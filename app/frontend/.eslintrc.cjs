module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh'],
  rules: {
    'react-refresh/only-export-components': [
      'warn',
      {
        allowConstantExport: true,
        // cva variant builders and context hooks live alongside their
        // components by convention (shadcn/ui, React context). Colocating
        // them costs fast refresh granularity, not correctness.
        allowExportNames: [
          'badgeVariants',
          'buttonVariants',
          'useSidebar',
          'useFlowContext',
          'useNodeContext',
        ],
      },
    ],
  },
}
