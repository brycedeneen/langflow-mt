import { lazy, memo, Suspense } from "react";
import ConfirmationModal from "@/modals/confirmationModal";
import EditNodeModal from "@/modals/editNodeModal";
import ShareModal from "@/modals/shareModal";

// Lazy-load CodeAreaModal — pulls in react-ace + ace-builds (~85KB minified).
// The modal only renders once the user opens it, so the chunk is deferred until
// then.
const CodeAreaModal = lazy(() => import("@/modals/codeAreaModal"));
import type { APIClassType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { useCustomComponentsAllowed } from "@/utils/customComponentGuards";

interface ToolbarModalsProps {
  // Modal visibility states
  showModalAdvanced: boolean;
  showconfirmShare: boolean;
  showOverrideModal: boolean;
  openModal: boolean;
  hasCode: boolean;

  // Setters for modal states
  setShowModalAdvanced: (value: boolean) => void;
  setShowconfirmShare: (value: boolean) => void;
  setShowOverrideModal: (value: boolean) => void;
  setOpenModal: (value: boolean) => void;

  // Data and handlers
  data: any;
  flowComponent: FlowType;
  handleOnNewValue: (value: string | string[]) => void;
  handleNodeClass: (apiClassType: APIClassType, type: string) => void;
  setToolMode: (value: boolean) => void;
  setSuccessData: (data: { title: string }) => void;
  addFlow: (params: { flow: FlowType; override: boolean }) => void;
  name?: string;
}

const ToolbarModals = memo(
  ({
    showModalAdvanced,
    showconfirmShare,
    showOverrideModal,
    openModal,
    hasCode,
    setShowModalAdvanced,
    setShowconfirmShare,
    setShowOverrideModal,
    setOpenModal,
    data,
    flowComponent,
    handleOnNewValue,
    handleNodeClass,
    setToolMode,
    setSuccessData,
    addFlow,
    name = "code",
  }: ToolbarModalsProps) => {
    // Force read-only editing for gated tenants (Task 10).
    const customAllowed = useCustomComponentsAllowed();

    // Handlers for confirmation modal
    const handleConfirm = () => {
      addFlow({
        flow: flowComponent,
        override: true,
      });
      setSuccessData({ title: `${data.id} successfully overridden!` });
      setShowOverrideModal(false);
    };

    const handleClose = () => {
      setShowOverrideModal(false);
    };

    const handleCancel = () => {
      addFlow({
        flow: flowComponent,
        override: true,
      });
      setSuccessData({ title: "New component successfully saved!" });
      setShowOverrideModal(false);
    };

    return (
      <>
        {showModalAdvanced && (
          <EditNodeModal
            data={data}
            open={showModalAdvanced}
            setOpen={setShowModalAdvanced}
          />
        )}

        {showconfirmShare && (
          <ShareModal
            open={showconfirmShare}
            setOpen={setShowconfirmShare}
            is_component={true}
            component={flowComponent}
          />
        )}

        {showOverrideModal && (
          <ConfirmationModal
            open={showOverrideModal}
            title="Replace"
            onConfirm={handleConfirm}
            onClose={handleClose}
            onCancel={handleCancel}
            cancelText="Create New"
            confirmationText="Replace"
            size="x-small"
            icon="SaveAll"
            index={6}
          >
            <ConfirmationModal.Content>
              <span>
                It seems {data.node?.display_name} already exists. Do you want
                to replace it with the current or create a new one?
              </span>
            </ConfirmationModal.Content>
          </ConfirmationModal>
        )}

        {hasCode && openModal && (
          <div className="hidden">
            <Suspense fallback={null}>
              <CodeAreaModal
                setValue={handleOnNewValue}
                open={openModal}
                setOpen={setOpenModal}
                dynamic={true}
                setNodeClass={(apiClassType, type) => {
                  handleNodeClass(apiClassType, type);
                  setToolMode(false);
                }}
                nodeClass={data.node}
                value={data.node?.template[name]?.value ?? ""}
                componentId={data.id}
                readonly={!customAllowed}
              >
                <></>
              </CodeAreaModal>
            </Suspense>
          </div>
        )}
      </>
    );
  },
);

ToolbarModals.displayName = "ToolbarModals";

export default ToolbarModals;
