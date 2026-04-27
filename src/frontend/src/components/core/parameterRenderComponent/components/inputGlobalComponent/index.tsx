import { memo, useEffect } from "react";
import { areInputPropsEqual } from "@/components/core/parameterRenderComponent/areInputPropsEqual";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import GeneralDeleteConfirmationModal from "@/shared/components/delete-confirmation-modal";
import { isAutosecretMarker } from "@/utils/autosecret";
import { looksLikeVariableName } from "../../../../../utils/reactflowUtils";
import { cn } from "../../../../../utils/utils";
import { Plus } from "lucide-react";
import { CommandItem } from "../../../../ui/command";
import GlobalVariableModal from "../../../GlobalVariableModal/GlobalVariableModal";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { InputGlobalComponentType, InputProps } from "../../types";
import InputComponent from "../inputComponent";
import {
  useGlobalVariableValue,
  useInitialLoad,
  useUnavailableField,
} from "./hooks";
import type { GlobalVariable, GlobalVariableHandlers } from "./types";

const STORED_SECRET_PLACEHOLDER = "•••••• Stored — type to replace";

function InputGlobalComponent({
  display_name,
  disabled,
  handleOnNewValue,
  value,
  id,
  load_from_db,
  password,
  editNode = false,
  placeholder,
  isToolMode = false,
  hasRefreshButton = false,
  showParameter = true,
}: InputProps<string, InputGlobalComponentType>): JSX.Element | null {
  const { data: globalVariables } = useGetGlobalVariables();

  // // Safely cast the data to our typed interface
  const typedGlobalVariables: GlobalVariable[] = globalVariables ?? [];
  const currentValue = value ?? "";
  const isDisabled = disabled ?? false;
  const loadFromDb = load_from_db ?? false;

  // // Extract complex logic into custom hooks
  const valueExists = useGlobalVariableValue(
    currentValue,
    typedGlobalVariables,
  );
  const unavailableField = useUnavailableField(display_name, currentValue);
  const isStoredAutosecret = loadFromDb && isAutosecretMarker(currentValue);

  useInitialLoad(
    isDisabled,
    loadFromDb,
    currentValue,
    typedGlobalVariables,
    valueExists || isStoredAutosecret,
    unavailableField,
    handleOnNewValue,
  );

  // Clean up when selected variable no longer exists. Autosecret markers are
  // valid stored references (not global variables), so leave them alone.
  useEffect(() => {
    if (
      loadFromDb &&
      currentValue &&
      !valueExists &&
      !isDisabled &&
      !isAutosecretMarker(currentValue)
    ) {
      handleOnNewValue(
        { value: "", load_from_db: false },
        { skipSnapshot: true },
      );
    }
  }, [
    loadFromDb,
    currentValue,
    valueExists,
    isDisabled,
    handleOnNewValue,
  ]);

  // Create handlers object for better organization
  const handlers: GlobalVariableHandlers = {
    // Handler for deleting global variables
    handleVariableDelete: (variableName: string) => {
      if (value === variableName) {
        handleOnNewValue({
          value: "",
          load_from_db: false,
        });
      }
    },

    // Handler for selecting a global variable
    handleVariableSelect: (selectedValue: string) => {
      handleOnNewValue({
        value: selectedValue,
        load_from_db: selectedValue !== "",
      });
    },

    // Handler for input changes
    handleInputChange: (inputValue: string, skipSnapshot?: boolean) => {
      handleOnNewValue(
        { value: inputValue, load_from_db: false },
        { skipSnapshot },
      );
    },
  };

  // Render add new variable button
  const renderAddVariableButton = () => (
    <GlobalVariableModal referenceField={display_name} disabled={disabled}>
      <CommandItem value="doNotFilter-addNewVariable">
        <Plus
          className={cn("mr-2 h-4 w-4 text-primary")}
          aria-hidden="true"
        />
        <span>Add New Variable</span>
      </CommandItem>
    </GlobalVariableModal>
  );

  // Render delete button for each option
  const renderDeleteButton = (option: string) => (
    <GeneralDeleteConfirmationModal
      option={option}
      onConfirmDelete={() => handlers.handleVariableDelete(option)}
    />
  );

  let variableOptions = typedGlobalVariables.map((variable) => variable.name);

  const isEnvVarName =
    password && currentValue && looksLikeVariableName(currentValue);
  if (
    (loadFromDb &&
      currentValue &&
      !valueExists &&
      !variableOptions.includes(currentValue) &&
      !isStoredAutosecret) ||
    (isEnvVarName && !variableOptions.includes(currentValue))
  ) {
    variableOptions = [...variableOptions, currentValue];
  }

  // For autosecret markers: hide the marker text from the UI (no chip, no
  // raw value in the input) but keep the marker in component state so the
  // backend's branch-3 passthrough preserves it on save. The placeholder
  // gives the user a visual indicator that a secret is stored.
  const selectedOption =
    !isStoredAutosecret && (loadFromDb || isEnvVarName) ? currentValue : "";
  const displayValue = isStoredAutosecret ? "" : currentValue;
  const displayPlaceholder = isStoredAutosecret
    ? STORED_SECRET_PLACEHOLDER
    : getPlaceholder(disabled, placeholder);

  if (!showParameter) {
    return null;
  }

  return (
    <InputComponent
      nodeStyle
      popoverWidth="17.5rem"
      placeholder={displayPlaceholder}
      id={id}
      editNode={editNode}
      disabled={disabled}
      password={password ?? false}
      value={displayValue}
      options={variableOptions}
      optionsPlaceholder="Global Variables"
      optionsIcon="Globe"
      optionsButton={renderAddVariableButton()}
      optionButton={renderDeleteButton}
      selectedOption={selectedOption}
      setSelectedOption={handlers.handleVariableSelect}
      onChange={handlers.handleInputChange}
      isToolMode={isToolMode}
      hasRefreshButton={hasRefreshButton}
    />
  );
}

export default memo(InputGlobalComponent, areInputPropsEqual);
