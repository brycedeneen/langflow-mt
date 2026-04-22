import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  type CellComponentProps,
  Grid,
  type GridImperativeAPI,
} from "react-window";
import IconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

const COLUMN_COUNT = 6;
const CELL_SIZE = 40;
const GRID_HEIGHT = 240;
const GRID_WIDTH = COLUMN_COUNT * CELL_SIZE;

type Props = {
  names: string[];
  selected: string;
  onSelect: (name: string) => void;
};

export default function IconGrid({ names, selected, onSelect }: Props) {
  const cellIdPrefix = useId();
  const [focusIndex, setFocusIndex] = useState<number>(() => {
    const i = names.indexOf(selected);
    return i >= 0 ? i : 0;
  });
  const gridRef = useRef<GridImperativeAPI>(null);

  // Re-clamp focus when the names list shrinks (e.g. user types and filters down).
  useEffect(() => {
    setFocusIndex((prev) =>
      prev >= names.length ? Math.max(0, names.length - 1) : prev,
    );
  }, [names.length]);

  // Scroll the focused cell into view as it changes.
  useEffect(() => {
    const rowIndex = Math.floor(focusIndex / COLUMN_COUNT);
    const columnIndex = focusIndex % COLUMN_COUNT;
    gridRef.current?.scrollToCell({
      rowIndex,
      columnIndex,
      rowAlign: "smart",
      columnAlign: "smart",
    });
  }, [focusIndex]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (names.length === 0) return;
      const lastIndex = names.length - 1;
      let next = focusIndex;
      switch (e.key) {
        case "ArrowRight":
          next = Math.min(lastIndex, focusIndex + 1);
          break;
        case "ArrowLeft":
          next = Math.max(0, focusIndex - 1);
          break;
        case "ArrowDown":
          next = Math.min(lastIndex, focusIndex + COLUMN_COUNT);
          break;
        case "ArrowUp":
          next = Math.max(0, focusIndex - COLUMN_COUNT);
          break;
        case "Home":
          next = 0;
          break;
        case "End":
          next = lastIndex;
          break;
        case "Enter":
        case " ":
          e.preventDefault();
          onSelect(names[focusIndex]);
          return;
        default:
          return;
      }
      e.preventDefault();
      setFocusIndex(next);
    },
    [focusIndex, names, onSelect],
  );

  // Cell re-renders on every focusIndex change because isFocused is derived
  // from it. Acceptable for ~30 visible cells; don't try to drop focusIndex
  // from the deps without also re-deriving isFocused some other way.
  const Cell = useCallback(
    ({ columnIndex, rowIndex, style }: CellComponentProps) => {
      const index = rowIndex * COLUMN_COUNT + columnIndex;
      if (index >= names.length) return null;
      const name = names[index];
      const isSelected = name === selected;
      const isFocused = index === focusIndex;
      return (
        <button
          id={`${cellIdPrefix}-${index}`}
          type="button"
          role="option"
          aria-selected={isSelected}
          tabIndex={-1}
          onClick={() => onSelect(name)}
          style={style}
          className={cn(
            "flex items-center justify-center rounded-sm",
            isSelected && "bg-accent text-accent-foreground",
            isFocused && "ring-2 ring-primary ring-inset",
          )}
          title={name}
        >
          <IconComponent name={name} className="h-5 w-5" />
        </button>
      );
    },
    [names, selected, focusIndex, onSelect, cellIdPrefix],
  );

  if (names.length === 0) return null;

  const rowCount = Math.ceil(names.length / COLUMN_COUNT);

  return (
    <div
      tabIndex={0}
      role="listbox"
      aria-label="Icons"
      aria-activedescendant={`${cellIdPrefix}-${focusIndex}`}
      onKeyDown={handleKeyDown}
      className="outline-hidden"
    >
      <Grid
        gridRef={gridRef}
        columnCount={COLUMN_COUNT}
        rowCount={rowCount}
        columnWidth={CELL_SIZE}
        rowHeight={CELL_SIZE}
        defaultHeight={GRID_HEIGHT}
        defaultWidth={GRID_WIDTH}
        cellComponent={Cell}
        cellProps={{}}
        style={{ height: GRID_HEIGHT, width: GRID_WIDTH }}
      />
    </div>
  );
}
