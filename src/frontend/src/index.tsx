import { AllCommunityModule, ModuleRegistry } from "ag-grid-community";
import ReactDOM from "react-dom/client";
import reportWebVitals from "./reportWebVitals";

ModuleRegistry.registerModules([AllCommunityModule]);

import "./style/classes.css";
// @ts-ignore
import "./style/index.css";
// @ts-ignore
import "./App.css";
import "./style/applies.css";

// @ts-ignore
import App from "./customization/custom-App";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);

root.render(<App />);
reportWebVitals();
