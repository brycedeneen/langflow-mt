import { Transition } from "@headlessui/react";
import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import IconComponent from "../../components/common/genericIconComponent";
import type { ErrorAlertType } from "../../types/alerts";

export default function ErrorAlert({
  title,
  list = [],
  id,
  removeAlert,
}: ErrorAlertType): JSX.Element {
  const [show, setShow] = useState(true);
  useEffect(() => {
    if (show) {
      setTimeout(() => {
        setShow(false);
        setTimeout(() => {
          removeAlert(id);
        }, 500);
      }, 5000);
    }
  }, [id, removeAlert, show]);

  return (
    <Transition
      show={show}
      appear={true}
      enter="transition-transform duration-500 ease-out"
      enterFrom={"transform translate-x-[-100%]"}
      enterTo={"transform translate-x-0"}
      leave="transition-transform duration-500 ease-in"
      leaveFrom={"transform translate-x-0"}
      leaveTo={"transform translate-x-[-100%]"}
    >
      <div
        onClick={() => {
          setShow(false);
          setTimeout(() => {
            removeAlert(id);
          }, 500);
        }}
        className="mt-6 w-96 rounded-md bg-error-background p-4 shadow-xl noflow nowheel nopan nodelete nodrag"
      >
        <div className="flex">
          <div className="shrink-0">
            <IconComponent
              name="XCircle"
              className="h-5 w-5 text-status-red"
              aria-hidden="true"
            />
          </div>
          <div className="ml-3">
            <h3 className="text-error-foreground word-break-break-word text-sm font-medium line-clamp-2">{title}</h3>
            {list?.length !== 0 &&
            list?.some((item) => item !== null && item !== undefined) ? (
              <div className="mt-2 text-sm text-error-foreground">
                <ul className="list-disc space-y-1 pl-5 align-top">
                  {list.map((item, index) => (
                    <li key={index} className="word-break-break-word">
                      <span className="align-text-top">
                        <Markdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            a: ({ node, ...props }) => (
                              <a
                                {...props}
                                target="_blank"
                                className="underline"
                                rel="noopener noreferrer"
                              >
                                {props.children}
                              </a>
                            ),
                            p({ node, ...props }) {
                              return (
                                <span className="inline-block w-fit max-w-full align-text-top truncate-multiline">
                                  {props.children}
                                </span>
                              );
                            },
                          }}
                        >
                          {Array.isArray(item) ? item.join("\n") : item}
                        </Markdown>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <></>
            )}
          </div>
        </div>
      </div>
    </Transition>
  );
}
