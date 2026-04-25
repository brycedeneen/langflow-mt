import { memo } from "react";

// memo: pure leaf with a single string prop, rendered inside ShadTooltip content
// inside NodeInputField (which re-renders on many flow store updates).
function NodeInputInfo({ info }: { info: string }) {
  return (
    <div className="h-full w-full break-words">
      {info.split("\n").map((line, index) => (
        <p key={index} className="block">
          {line}
        </p>
      ))}
    </div>
  );
}

export default memo(NodeInputInfo);
