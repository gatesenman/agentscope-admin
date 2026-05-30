import { defineConfig } from '@vben/eslint-config';

export default defineConfig([
  {
    // The Python backend (and its virtualenv) lives under `server/` and must
    // not be linted by the frontend ESLint pipeline.
    ignores: ['server/**'],
  },
]);
