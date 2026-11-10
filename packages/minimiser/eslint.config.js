import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.strict,
  { rules: { "no-console": "error" } },
  { files: ["test/**/*.ts"], rules: { "@typescript-eslint/no-non-null-assertion": "off" } },
);
