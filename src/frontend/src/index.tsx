import ReactDOM from "react-dom/client";
import reportWebVitals from "./reportWebVitals";

import "./style/classes.css";
// @ts-ignore
import "./style/index.css";
// @ts-ignore
import "./style/custom-ace-overrides.css";

// @ts-ignore
import App from "./customization/custom-App";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);

root.render(<App />);
reportWebVitals();
