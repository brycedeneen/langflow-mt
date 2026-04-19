import { Button } from "@/components/ui/button";
import { runTestForAll } from "@/utils/test-runs";

type Props = {
  anyTesting: boolean;
};

export function TestAllButton({ anyTesting }: Props) {
  return (
    <Button
      size="sm"
      disabled={anyTesting}
      onClick={() => {
        void runTestForAll();
      }}
    >
      Test All
    </Button>
  );
}
