import BaseModal from "../../../modals/baseModal";
import type { fetchErrorComponentType } from "../../../types/components";
import { Unplug } from "lucide-react";

export default function FetchErrorComponent({
  message,
  description,
  openModal,
  setRetry,
  isLoadingHealth,
}: fetchErrorComponentType) {
  return (
    <>
      <BaseModal
        size="small-h-full"
        open={openModal}
        type="modal"
        onSubmit={() => {
          setRetry();
        }}
      >
        <BaseModal.Content>
          <div role="status" className="m-auto flex flex-col items-center">
            <Unplug
              className={`h-16 w-16`}
            />
            <br></br>
            <span className="text-lg text-primary">{message}</span>
            <span className="text-lg text-primary">{description}</span>
          </div>
        </BaseModal.Content>

        <BaseModal.Footer
          submit={{
            label: "Retry",
            loading: isLoadingHealth,
            onClick: () => {
              setRetry();
            },
          }}
        />
      </BaseModal>
    </>
  );
}
