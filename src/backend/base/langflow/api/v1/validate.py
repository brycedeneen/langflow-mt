from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from lfx.base.prompts.api_utils import process_prompt_template
from lfx.components.processing._data_mapper import MapperConfig
from lfx.custom.validate import validate_code
from lfx.log.logger import logger
from pydantic import ValidationError as _PydanticValidationError

from langflow.api.v1.base import Code, CodeValidationResponse, PromptValidationResponse, ValidatePromptRequest
from langflow.services.auth.utils import get_current_active_user

# build router
router = APIRouter(prefix="/validate", tags=["Validate"])


@router.post("/code", status_code=200, dependencies=[Depends(get_current_active_user)], include_in_schema=False)
async def post_validate_code(code: Code) -> CodeValidationResponse:
    try:
        errors = validate_code(code.code)
        return CodeValidationResponse(
            imports=errors.get("imports", {}),
            function=errors.get("function", {}),
        )
    except Exception as e:
        logger.debug("Error validating code", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/prompt", status_code=200, dependencies=[Depends(get_current_active_user)], include_in_schema=False)
async def post_validate_prompt(
    prompt_request: ValidatePromptRequest,
) -> PromptValidationResponse:
    try:
        if not prompt_request.frontend_node:
            return PromptValidationResponse(
                input_variables=[],
                frontend_node=None,
            )

        # Process the prompt template using direct attributes
        input_variables = process_prompt_template(
            template=prompt_request.template,
            name=prompt_request.name,
            custom_fields=prompt_request.frontend_node.custom_fields,
            frontend_node_template=prompt_request.frontend_node.template,
            is_mustache=prompt_request.mustache,
        )

        return PromptValidationResponse(
            input_variables=input_variables,
            frontend_node=prompt_request.frontend_node,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/validate-mapping-config", status_code=200, dependencies=[Depends(get_current_active_user)])
async def validate_mapping_config(body: dict) -> JSONResponse:
    """Validate a Data Mapper mapping_config blob against the Pydantic schema.

    Returns ``{"errors": []}`` on success (HTTP 200) or ``{"errors": [{path, message}]}``
    on failure (HTTP 422).  Each error item is ``{path: list[str|int], message: str}``
    so the modal can attach an inline error to the specific row / field.

    Uses ``JSONResponse`` to control the body shape precisely — the 422 body is
    ``{"errors": [...]}`` directly, without the ``{"detail": ...}`` envelope that
    FastAPI adds when using ``HTTPException``.
    """
    try:
        MapperConfig.model_validate(body)
    except _PydanticValidationError as e:
        errors = [{"path": list(err["loc"]), "message": err["msg"]} for err in e.errors()]
        return JSONResponse(status_code=422, content={"errors": errors})
    return JSONResponse(status_code=200, content={"errors": []})
