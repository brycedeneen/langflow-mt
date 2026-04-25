/**
 * enum for the different types of nodes
 * @enum
 */
export const TypeModal = {
  TEXT: 1,
  PROMPT: 2,
} as const;
export type TypeModal = (typeof TypeModal)[keyof typeof TypeModal];

export const BuildStatus = {
  BUILDING: "BUILDING",
  TO_BUILD: "TO_BUILD",
  BUILT: "BUILT",
  INACTIVE: "INACTIVE",
  ERROR: "ERROR",
} as const;
export type BuildStatus = (typeof BuildStatus)[keyof typeof BuildStatus];

export const InputOutput = {
  INPUT: "input",
  OUTPUT: "output",
} as const;
export type InputOutput = (typeof InputOutput)[keyof typeof InputOutput];

export const IOInputTypes = {
  TEXT: "TextInput",
  FILE_LOADER: "FileLoader",
  KEYPAIR: "KeyPairInput",
  JSON: "JsonInput",
  STRING_LIST: "StringListInput",
} as const;
export type IOInputTypes = (typeof IOInputTypes)[keyof typeof IOInputTypes];

export const IOOutputTypes = {
  TEXT: "TextOutput",
  PDF: "PDFOutput",
  CSV: "CSVOutput",
  IMAGE: "ImageOutput",
  JSON: "JsonOutput",
  KEY_PAIR: "KeyPairOutput",
  STRING_LIST: "StringListOutput",
  DATA: "DataOutput",
} as const;
export type IOOutputTypes = (typeof IOOutputTypes)[keyof typeof IOOutputTypes];

export const EventDeliveryType = {
  STREAMING: "streaming",
  POLLING: "polling",
  DIRECT: "direct",
} as const;
export type EventDeliveryType =
  (typeof EventDeliveryType)[keyof typeof EventDeliveryType];
