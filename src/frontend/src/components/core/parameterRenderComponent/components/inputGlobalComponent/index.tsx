import { memo, useEffect } from "react";
import { areInputPropsEqual } from "@/components/core/parameterRenderComponent/areInputPropsEqual";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import GeneralDeleteConfirmationModal from "@/shared/components/delete-confirmation-modal";
import { looksLikeVariableName } from "../../../../../utils/reactflowUtils";
import { cn } from "../../../../../utils/utils";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
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

// Sentinel prefix the backend writes to a SecretStrInput's `value` after it
// promotes a typed plaintext secret into a Vault-backed auto-Variable. The
// underlying variable is filtered out of /api/v1/variables, so without
// special-casing here the marker reads as an "orphaned global variable" and
// triggers the cleanup path that blanks the field on reload.
const AUTOSECRET_VALUE_PREFIX = "__autosecret|";

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

  const isAutosecret =
    typeof currentValue === "string" &&
    currentValue.startsWith(AUTOSECRET_VALUE_PREFIX);
  // Treat marker-backed values as "valid stored secret" so the cleanup paths
  // below don't blank them.
  const effectiveValueExists = valueExists || isAutosecret;

  useInitialLoad(
    isDisabled,
    loadFromDb,
    typedGlobalVariables,
    effectiveValueExists,
    unavailableField,
    handleOnNewValue,
  );

  // Clean up when selected variable no longer exists
  useEffect(() => {
    if (loadFromDb && currentValue && !effectiveValueExists && !isDisabled) {
      handleOnNewValue(
        { value: "", load_from_db: false },
        { skipSnapshot: true },
      );
    }
  }, [
    loadFromDb,
    currentValue,
    effectiveValueExists,
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
        <ForwardedIconComponent
          name="Plus"
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
    !isAutosecret &&
    ((loadFromDb &&
      currentValue &&
      !valueExists &&
      !variableOptions.includes(currentValue)) ||
      (isEnvVarName && !variableOptions.includes(currentValue)))
  ) {
    variableOptions = [...variableOptions, currentValue];
  }

  const selectedOption = isAutosecret
    ? ""
    : loadFromDb || isEnvVarName
      ? currentValue
      : "";

  // Hide the raw marker from the rendered input — show a placeholder hinting
  // the secret is already stored. The marker stays in flow state so a no-op
  // save round-trips correctly through the backend's preserve-marker branch.
  const displayedValue = isAutosecret ? "" : currentValue;
  const displayedPlaceholder = isAutosecret
    ? "Stored — type to replace"
    : getPlaceholder(disabled, placeholder);

  if (!showParameter) {
    return null;
  }

  return (
    <InputComponent
      nodeStyle
      popoverWidth="17.5rem"
      placeholder={displayedPlaceholder}
      id={id}
      editNode={editNode}
      disabled={disabled}
      password={password ?? false}
      value={displayedValue}
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
