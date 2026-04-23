import * as Form from "@radix-ui/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useContext, useState } from "react";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useLoginUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import { useSanitizeRedirectUrl } from "@/hooks/use-sanitize-redirect-url";
import { SIGNIN_ERROR_ALERT } from "../../constants/alerts_constants";
import { CONTROL_LOGIN_STATE } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import useAlertStore from "../../stores/alertStore";
import type { LoginType } from "../../types/api";
import type {
  inputHandlerEventType,
  loginInputStateType,
} from "../../types/components";
import { cn } from "../../utils/utils";

const inputClasses = cn(
  "flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm",
  "ring-offset-background placeholder:text-muted-foreground",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground focus-visible:ring-offset-2",
  "disabled:cursor-not-allowed disabled:opacity-50",
);

export default function LoginPage(): JSX.Element {
  const [inputState, setInputState] =
    useState<loginInputStateType>(CONTROL_LOGIN_STATE);
  const [showPassword, setShowPassword] = useState(false);

  const { password, username } = inputState;

  useSanitizeRedirectUrl();

  const { login, clearAuthSession } = useContext(AuthContext);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  const { mutate } = useLoginUser();
  const queryClient = useQueryClient();

  function signIn() {
    const user: LoginType = {
      username: username.trim(),
      password: password.trim(),
    };

    mutate(user, {
      onSuccess: (data) => {
        clearAuthSession();
        login(data.access_token, "login", data.refresh_token);
        queryClient.clear();
      },
      onError: (error) => {
        setErrorData({
          title: SIGNIN_ERROR_ALERT,
          list: [error["response"]["data"]["detail"]],
        });
      },
    });
  }

  return (
    <Form.Root
      onSubmit={(event) => {
        event.preventDefault();
        if (password === "") return;
        signIn();
      }}
      className="login-form h-screen w-full"
    >
      <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
        <div className="flex w-72 flex-col items-center justify-center gap-2">
          <LangflowLogo
            title="Amplify logo"
            className="mb-4 h-10 w-10 scale-[1.5]"
          />
          <span className="mb-6 text-2xl font-semibold text-primary">
            Sign in to Amplify
          </span>

          <div className="mb-3 w-full">
            <Form.Field name="username">
              <Form.Label asChild>
                <Label className="data-[invalid]:label-invalid">
                  Username{" "}
                  <span className="font-medium text-destructive">*</span>
                </Label>
              </Form.Label>
              <Form.Control asChild>
                <input
                  type="text"
                  autoComplete="username"
                  placeholder="Username"
                  value={username}
                  required
                  onChange={(e) =>
                    handleInput({
                      target: { name: "username", value: e.target.value },
                    })
                  }
                  className={cn(inputClasses, "mt-2")}
                />
              </Form.Control>
              <Form.Message match="valueMissing" className="field-invalid">
                Please enter your username
              </Form.Message>
            </Form.Field>
          </div>

          <div className="mb-3 w-full">
            <Form.Field name="password">
              <Form.Label asChild>
                <Label className="data-[invalid]:label-invalid">
                  Password{" "}
                  <span className="font-medium text-destructive">*</span>
                </Label>
              </Form.Label>
              <div className="relative mt-2">
                <Form.Control asChild>
                  <input
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Password"
                    value={password}
                    required
                    onChange={(e) =>
                      handleInput({
                        target: { name: "password", value: e.target.value },
                      })
                    }
                    className={cn(inputClasses, "pr-10")}
                  />
                </Form.Control>
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={
                    showPassword ? "Hide password" : "Show password"
                  }
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground hover:text-foreground"
                >
                  <ForwardedIconComponent
                    name={showPassword ? "Eye" : "EyeOff"}
                    className="h-5 w-5"
                  />
                </button>
              </div>
              <Form.Message match="valueMissing" className="field-invalid">
                Please enter your password
              </Form.Message>
            </Form.Field>
          </div>

          <div className="w-full">
            <Form.Submit asChild>
              <Button className="mr-3 mt-6 w-full" type="submit">
                Sign in
              </Button>
            </Form.Submit>
          </div>
          <div className="w-full">
            <CustomLink to="/signup">
              <Button className="w-full" variant="outline" type="button">
                Don't have an account?&nbsp;<b>Sign Up</b>
              </Button>
            </CustomLink>
          </div>
        </div>
      </div>
    </Form.Root>
  );
}
