// three ships no bundled types; @types/three (devDependency) provides them for
// `three` and `three/examples/jsm/*`. The code imports OrbitControls via the
// `three/addons/*` alias (resolved by Vite), which @types/three doesn't map —
// re-export the typed class from the examples path so tsc resolves it.
declare module 'three/addons/controls/OrbitControls.js' {
  export { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
}
