/**
 * Lazy registration helper for ag-grid-community modules.
 *
 * Eagerly importing `ag-grid-community` at app boot pulls ~80-100 KB into the
 * initial bundle even though no table renders until the user opens a modal
 * that uses one. This helper defers the import + `ModuleRegistry.registerModules`
 * call to the first time a table is about to mount.
 *
 * Usage:
 *   const [ready, setReady] = useState(false);
 *   useEffect(() => {
 *     ensureAgGridRegistered().then(() => setReady(true));
 *   }, []);
 *   if (!ready) return <Spinner />;
 *   return <AgGridReact ... />;
 *
 * Subsequent calls return the same memoized Promise (no-op after the first).
 */
let registrationPromise: Promise<void> | null = null;

export function ensureAgGridRegistered(): Promise<void> {
  if (registrationPromise) return registrationPromise;
  registrationPromise = import("ag-grid-community").then(
    ({ AllCommunityModule, ModuleRegistry }) => {
      ModuleRegistry.registerModules([AllCommunityModule]);
    },
  );
  return registrationPromise;
}
