import { useRef, useState } from "react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import InputGlobalComponent from "../inputGlobalComponent";
import type { InputProps } from "../../types";

export type TextFileSecretComponentType = {
  file_types?: string[];
  display_name?: string;
  load_from_db?: boolean;
};

function softValidate(text: string): string {
  if (text && !(text.includes("-----BEGIN ") && text.includes("-----END "))) {
    return "Doesn't look like a PEM. Continue anyway if you're sure.";
  }
  return "";
}

export default function TextFileSecretComponent({
  id,
  value,
  handleOnNewValue,
  disabled,
  file_types,
  editNode,
  nodeClass,
  handleNodeClass,
  nodeId,
  helperText,
  readonly,
  placeholder,
  isToolMode,
  nodeInformationMetadata,
  hasRefreshButton,
  showParameter,
  inspectionPanel,
  display_name,
  load_from_db,
}: InputProps<string, TextFileSecretComponentType>) {
  const defaultTab = value ? "paste" : "upload";
  const [mode, setMode] = useState<string>(defaultTab);
  const [warn, setWarn] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const accept = file_types?.length
    ? file_types.map((t) => `.${t}`).join(",")
    : undefined;

  const handleFileChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 1_000_000) {
      const kb = Math.round(file.size / 1024);
      setWarn(`File is ${kb} KB — max is 1 MB. Select a smaller file.`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const text = await file.text();
    // Reset file input so selecting the same filename re-triggers change
    if (fileInputRef.current) fileInputRef.current.value = "";

    handleOnNewValue({ value: text });
    setWarn(softValidate(text));
  };

  const baseInputProps = {
    id,
    value: value ?? "",
    editNode: editNode ?? false,
    handleOnNewValue,
    disabled: disabled ?? false,
    nodeClass,
    handleNodeClass,
    nodeId,
    helperText,
    readonly,
    placeholder,
    isToolMode,
    nodeInformationMetadata,
    hasRefreshButton,
    showParameter,
    inspectionPanel,
  };

  return (
    <div className="w-full">
      <Tabs value={mode} onValueChange={(v) => { setMode(v); setWarn(""); }}>
        <TabsList>
          <TabsTrigger value="upload">Upload File</TabsTrigger>
          <TabsTrigger value="paste">Paste</TabsTrigger>
        </TabsList>

        <TabsContent value="paste">
          <div onBlur={() => setWarn(softValidate(value ?? ""))}>
            <InputGlobalComponent
              {...baseInputProps}
              password={true}
              load_from_db={load_from_db}
              display_name={display_name ?? "Secret text"}
              id={`input-${id}`}
            />
          </div>
        </TabsContent>

        <TabsContent value="upload">
          <input
            ref={fileInputRef}
            type="file"
            accept={accept}
            disabled={disabled}
            onChange={handleFileChange}
            className="block w-full text-sm text-muted-foreground file:mr-4 file:rounded file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-foreground hover:file:bg-muted/80 disabled:pointer-events-none disabled:opacity-50"
          />
        </TabsContent>
      </Tabs>

      {warn && (
        <p role="alert" className="mt-2 text-sm text-yellow-600">
          {warn}
        </p>
      )}
    </div>
  );
}
