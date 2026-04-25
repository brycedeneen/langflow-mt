import ast
import json
from typing import Any

from langchain_classic.agents import Tool
from typing_extensions import override

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.inputs.inputs import BoolInput, DropdownInput, FieldTypes, HandleInput, MessageTextInput, MultilineInput
from lfx.io import Output
from lfx.log.logger import logger
from lfx.schema.dotdict import dotdict


class PythonCodeStructuredTool(LCToolComponent):
    DEFAULT_KEYS = [
        "code",
        "_type",
        "text_key",
        "tool_code",
        "tool_name",
        "tool_description",
        "return_direct",
        "tool_function",
        "global_variables",
        "_classes",
        "_functions",
    ]
    display_name = "Python Code Structured (Deactivated)"
    description = (
        "Deactivated: this component has been disabled because it executes user-provided "
        "Python code via exec(), which is unsafe. Use the Python REPL component instead."
    )
    documentation = "https://python.langchain.com/docs/modules/tools/custom_tools/#structuredtool-dataclass"
    name = "PythonCodeStructuredTool"
    icon = "Python"
    field_order = ["name", "description", "tool_code", "return_direct", "tool_function"]
    legacy: bool = True
    replacement = ["processing.PythonREPLComponent"]

    _DEACTIVATED_MESSAGE = (
        "PythonCodeStructuredTool has been deactivated because it executes user-provided "
        "code via exec(). Use the Python REPL component "
        "(processing.PythonREPLComponent) instead."
    )

    inputs = [
        MultilineInput(
            name="tool_code",
            display_name="Tool Code",
            info="Enter the dataclass code.",
            placeholder="def my_function(args):\n    pass",
            required=True,
            real_time_refresh=True,
            refresh_button=True,
        ),
        MessageTextInput(
            name="tool_name",
            display_name="Tool Name",
            info="Enter the name of the tool.",
            required=True,
        ),
        MessageTextInput(
            name="tool_description",
            display_name="Description",
            info="Enter the description of the tool.",
            required=True,
        ),
        BoolInput(
            name="return_direct",
            display_name="Return Directly",
            info="Should the tool return the function output directly?",
        ),
        DropdownInput(
            name="tool_function",
            display_name="Tool Function",
            info="Select the function for additional expressions.",
            options=[],
            required=True,
            real_time_refresh=True,
            refresh_button=True,
        ),
        HandleInput(
            name="global_variables",
            display_name="Global Variables",
            info="Enter the global variables or Create Data Component.",
            input_types=["Data", "JSON"],
            field_type=FieldTypes.DICT,
            is_list=True,
        ),
        MessageTextInput(name="_classes", display_name="Classes", advanced=True),
        MessageTextInput(name="_functions", display_name="Functions", advanced=True),
    ]

    outputs = [
        Output(display_name="Tool", name="result_tool", method="build_tool"),
    ]

    @override
    async def update_build_config(
        self, build_config: dotdict, field_value: Any, field_name: str | None = None
    ) -> dotdict:
        if field_name is None:
            return build_config

        if field_name not in {"tool_code", "tool_function"}:
            return build_config

        try:
            named_functions = {}
            [classes, functions] = self._parse_code(build_config["tool_code"]["value"])
            existing_fields = {}
            if len(build_config) > len(self.DEFAULT_KEYS):
                for key in build_config.copy():
                    if key not in self.DEFAULT_KEYS:
                        existing_fields[key] = build_config.pop(key)

            names = []
            for func in functions:
                named_functions[func["name"]] = func
                names.append(func["name"])

                for arg in func["args"]:
                    field_name = f"{func['name']}|{arg['name']}"
                    if field_name in existing_fields:
                        build_config[field_name] = existing_fields[field_name]
                        continue

                    field = MessageTextInput(
                        display_name=f"{arg['name']}: Description",
                        name=field_name,
                        info=f"Enter the description for {arg['name']}",
                        required=True,
                    )
                    build_config[field_name] = field.to_dict()
            build_config["_functions"]["value"] = json.dumps(named_functions)
            build_config["_classes"]["value"] = json.dumps(classes)
            build_config["tool_function"]["options"] = names
        except Exception as e:  # noqa: BLE001
            self.status = f"Failed to extract names: {e}"
            logger.debug(self.status, exc_info=True)
            build_config["tool_function"]["options"] = ["Failed to parse", str(e)]
        return build_config

    async def build_tool(self) -> Tool:
        # Hard gate — this component executes user-supplied Python via exec()
        # and is replaced by PythonREPLComponent. Refuse to run so flows that
        # still reference it surface a clear migration error instead of
        # silently executing arbitrary code. The original implementation
        # (4x exec() of self.tool_code, dynamic class/function definition,
        # etc.) is preserved in git history.
        raise RuntimeError(self._DEACTIVATED_MESSAGE)

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """This function is called after the code validation is done."""
        frontend_node = await super().update_frontend_node(new_frontend_node, current_frontend_node)
        frontend_node["template"] = await self.update_build_config(
            frontend_node["template"],
            frontend_node["template"]["tool_code"]["value"],
            "tool_code",
        )
        frontend_node = await super().update_frontend_node(new_frontend_node, current_frontend_node)
        for key in frontend_node["template"]:
            if key in self.DEFAULT_KEYS:
                continue
            frontend_node["template"] = await self.update_build_config(
                frontend_node["template"], frontend_node["template"][key]["value"], key
            )
            frontend_node = await super().update_frontend_node(new_frontend_node, current_frontend_node)
        return frontend_node

    def _parse_code(self, code: str) -> tuple[list[dict], list[dict]]:
        parsed_code = ast.parse(code)
        lines = code.split("\n")
        classes = []
        functions = []
        for node in parsed_code.body:
            if isinstance(node, ast.ClassDef):
                class_lines = lines[node.lineno - 1 : node.end_lineno]
                class_lines[-1] = class_lines[-1][: node.end_col_offset]
                class_lines[0] = class_lines[0][node.col_offset :]
                classes.append(
                    {
                        "name": node.name,
                        "code": class_lines,
                    }
                )
                continue

            if not isinstance(node, ast.FunctionDef):
                continue

            func = {"name": node.name, "args": []}
            for arg in node.args.args:
                if arg.lineno != arg.end_lineno:
                    msg = "Multiline arguments are not supported"
                    raise ValueError(msg)

                func_arg = {
                    "name": arg.arg,
                    "annotation": None,
                }

                for default in node.args.defaults:
                    if (
                        arg.lineno > default.lineno
                        or arg.col_offset > default.col_offset
                        or (
                            arg.end_lineno is not None
                            and default.end_lineno is not None
                            and arg.end_lineno < default.end_lineno
                        )
                        or (
                            arg.end_col_offset is not None
                            and default.end_col_offset is not None
                            and arg.end_col_offset < default.end_col_offset
                        )
                    ):
                        continue

                    if isinstance(default, ast.Name):
                        func_arg["default"] = default.id
                    elif isinstance(default, ast.Constant):
                        func_arg["default"] = str(default.value) if default.value is not None else None

                if arg.annotation:
                    annotation_line = lines[arg.annotation.lineno - 1]
                    annotation_line = annotation_line[: arg.annotation.end_col_offset]
                    annotation_line = annotation_line[arg.annotation.col_offset :]
                    func_arg["annotation"] = annotation_line
                    if isinstance(func_arg["annotation"], str) and func_arg["annotation"].count("=") > 0:
                        func_arg["annotation"] = "=".join(func_arg["annotation"].split("=")[:-1]).strip()
                if isinstance(func["args"], list):
                    func["args"].append(func_arg)
            functions.append(func)

        return classes, functions

    def _find_imports(self, code: str) -> dotdict:
        imports: list[str] = []
        from_imports = []
        parsed_code = ast.parse(code)
        for node in parsed_code.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                from_imports.append(node)
        return dotdict({"imports": imports, "from_imports": from_imports})

    def _get_value(self, value: Any, annotation: Any) -> Any:
        return value if isinstance(value, annotation) else value["value"]

    def _find_arg(self, named_functions: dict, func_name: str, arg_name: str) -> dict | None:
        for arg in named_functions[func_name]["args"]:
            if arg["name"] == arg_name:
                return arg
        return None
