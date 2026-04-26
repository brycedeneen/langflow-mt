import {
  PDFCheckFlow,
  PDFLoadErrorTitle,
} from "../../../../constants/constants";
import IconComponent from "../../../common/genericIconComponent";

export default function ErrorComponent(): JSX.Element {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
      <div className="flex-max-width h-full flex-col items-center justify-center text-center align-middle">
        <span className="flex gap-2">
          <IconComponent name="FileX2" />
          <span className="text-lg text-foreground">{PDFLoadErrorTitle}</span>
        </span>
        <br />
        <div className="langflow-chat-desc">
          <span className="langflow-chat-desc-span">{PDFCheckFlow} </span>
        </div>
      </div>
    </div>
  );
}
