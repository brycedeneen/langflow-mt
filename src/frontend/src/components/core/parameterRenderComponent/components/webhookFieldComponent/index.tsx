import { memo, useCallback, useContext, useEffect, useRef, useState } from "react";
import { areInputPropsEqual } from "@/components/core/parameterRenderComponent/areInputPropsEqual";
import { AuthContext } from "@/contexts/authContext";
import { useGetBuildsMutation } from "@/controllers/API/queries/_builds/use-get-builds-polling-mutation";
import SecretKeyModalButton from "@/customization/components/custom-secret-key-modal-button";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import { getModalPropsApiKey } from "@/customization/utils/get-modal-props";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type { InputProps, TextAreaComponentType } from "../../types";
import CopyFieldAreaComponent from "../copyFieldAreaComponent";
import TextAreaComponent from "../textAreaComponent";
import { AlertTriangle } from "lucide-react";
import IconComponent from "../../../../common/genericIconComponent";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../../../ui/dialog";
import { Button } from "../../../../ui/button";
import { Input } from "../../../../ui/input";
import { cn } from "../../../../../utils/utils";

function WebhookFieldComponent({
  value,
  handleOnNewValue,
  editNode = false,
  id = "",
  nodeInformationMetadata,
  showParameter = true,
  ...baseInputProps
}: InputProps<string, TextAreaComponentType>): JSX.Element | null {
  const { userData } = useContext(AuthContext);
  const [userId, setUserId] = useState("");
  const { mutate: getBuildsMutation } = useGetBuildsMutation();
  const hasInitialized = useRef(false);
  const modalProps = getModalPropsApiKey();

  const isBackendUrl = nodeInformationMetadata?.variableName === "endpoint";
  const isCurlWebhook = nodeInformationMetadata?.variableName === "curl";
  const isApiKey = nodeInformationMetadata?.variableName === "api_key";
  const isAuth = nodeInformationMetadata?.isAuth;
  const showGenerateToken =
    (isBackendUrl && !editNode && !isAuth) ||
    (ENABLE_DATASTAX_LANGFLOW && !editNode);

  useEffect(() => {
    const getBuilds =
      (!editNode && isBackendUrl && !hasInitialized.current) ||
      (ENABLE_DATASTAX_LANGFLOW && !editNode);

    if (getBuilds) {
      hasInitialized.current = true;
      getBuildsMutation({
        flowId: nodeInformationMetadata?.flowId!,
      });
    }
  }, []);

  useEffect(() => {
    if (userData) {
      setUserId(userData.id);
    }
  }, [userData]);

  if (!showParameter) {
    return null;
  }

  return (
    <div className="grid w-full gap-2">
      {isBackendUrl && (
        <div>
          <CopyFieldAreaComponent
            id={id}
            value={value}
            editNode={editNode}
            handleOnNewValue={handleOnNewValue}
            {...baseInputProps}
          />
        </div>
      )}

      {isCurlWebhook && (
        <div>
          <TextAreaComponent
            id={id}
            value={value}
            editNode={editNode}
            handleOnNewValue={handleOnNewValue}
            {...baseInputProps}
            nodeInformationMetadata={nodeInformationMetadata}
          />
        </div>
      )}

      {isApiKey && !editNode && (
        <div>
          <WebhookApiKeyField
            flowId={nodeInformationMetadata?.flowId ?? ""}
          />
        </div>
      )}

      {showGenerateToken && (
        <div>
          <SecretKeyModalButton userId={userId} modalProps={modalProps} />
        </div>
      )}
    </div>
  );
}

export default memo(WebhookFieldComponent, areInputPropsEqual);

function WebhookApiKeyField({ flowId }: { flowId: string }) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [hasExistingKey, setHasExistingKey] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  // Check if the flow already has a webhook (implying a key was provisioned)
  useEffect(() => {
    if (currentFlow?.webhook) {
      setHasExistingKey(true);
    }
  }, [currentFlow?.webhook]);

  const handleGenerateKey = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api.post(
        `${getURL("FLOWS")}/${flowId}/webhook-api-key`,
      );
      const key = response.data.api_key;
      setGeneratedKey(key);
      setHasExistingKey(true);
      setIsDialogOpen(true);
    } catch (error: any) {
      setErrorData({
        title: "Failed to generate API key",
        list: [error?.response?.data?.detail ?? error.message],
      });
    } finally {
      setIsLoading(false);
    }
  }, [flowId, setErrorData]);

  const handleCopy = useCallback(() => {
    if (generatedKey) {
      navigator.clipboard.writeText(generatedKey);
      setIsCopied(true);
      setSuccessData({ title: "API key copied to clipboard" });
      setTimeout(() => setIsCopied(false), 2000);
    }
  }, [generatedKey, setSuccessData]);

  const handleDialogClose = useCallback(() => {
    setIsDialogOpen(false);
    setGeneratedKey(null);
    setIsCopied(false);
  }, []);

  return (
    <>
      <Button
        variant={hasExistingKey ? "outline" : "default"}
        size="sm"
        className="w-full"
        onClick={handleGenerateKey}
        disabled={isLoading}
        data-testid="btn-generate-webhook-api-key"
      >
        <IconComponent
          name={isLoading ? "Loader2" : hasExistingKey ? "RefreshCw" : "Key"}
          className={cn("mr-2 h-4 w-4", isLoading && "animate-spin")}
        />
        {isLoading
          ? "Generating..."
          : hasExistingKey
            ? "Reset API Key"
            : "Generate API Key"}
      </Button>

      <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Webhook API Key</DialogTitle>
            <DialogDescription>
              Copy your API key now. You won't be able to see it again. If you
              lose it, you'll need to generate a new one.
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center gap-2">
            <Input
              value={generatedKey ?? ""}
              readOnly
              className="font-mono text-sm"
              data-testid="webhook-api-key-value"
            />
            <Button
              variant="outline"
              size="icon"
              onClick={handleCopy}
              data-testid="btn-copy-webhook-api-key"
            >
              <IconComponent
                name={isCopied ? "Check" : "Copy"}
                className="h-4 w-4"
              />
            </Button>
          </div>
          <div className="rounded-md border border-warning/50 bg-warning/10 p-3 text-sm text-warning-foreground">
            <div className="flex items-start gap-2">
              <AlertTriangle
                className="mt-0.5 h-4 w-4 shrink-0 text-warning"
              />
              <span>
                Include this key as the <code className="font-mono text-xs font-semibold">x-api-key</code> header in
                your webhook requests.
              </span>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={handleDialogClose}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
