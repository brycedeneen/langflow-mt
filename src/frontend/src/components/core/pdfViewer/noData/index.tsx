import { PDFErrorTitle, PDFLoadError } from "../../../../constants/constants";

export default function NoDataPdf(): JSX.Element {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
      <div className="flex-max-width h-full flex-col items-center justify-center text-center align-middle">
        <span>
          📄 <span className="text-lg text-foreground">{PDFErrorTitle}</span>
        </span>
        <br />
        <div className="langflow-chat-desc">
          <span className="langflow-chat-desc-span">{PDFLoadError} </span>
        </div>
      </div>
    </div>
  );
}
