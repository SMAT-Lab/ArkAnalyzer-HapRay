// eslint.config.mjs
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import globals from 'globals';
import { defineConfig } from 'eslint/config';

export default defineConfig([
    {
        files: ['src/**/*.ts'],
        ignores: [
            '**/node_modules/**',
            '**/dist/**',
            '**/build/**',
            '**/coverage/**',
            '**/lib/**',
            '**/*.js',
            '**/*.d.ts',
            'src/core/elf/demangle-wasm.js',
        ],
        languageOptions: {
            parser: tsParser,
            parserOptions: {
                ecmaVersion: 2022,
                sourceType: 'module',
                project: './tsconfig.json',
            },
            globals: {
                ...globals.browser,
                ...globals.node,
                ...globals.es2021,
            },
        },
        plugins: {
            '@typescript-eslint': tsPlugin,
        },
        rules: {
            // ====================== 类型安全规则 ======================
            // 禁止使用 any 类型
            '@typescript-eslint/no-explicit-any': 'warn',
            // 禁止不安全的参数传递
            '@typescript-eslint/no-unsafe-argument': 'error',
            // 禁止不安全的赋值
            '@typescript-eslint/no-unsafe-assignment': 'error',
            // 禁止不安全的函数调用
            '@typescript-eslint/no-unsafe-call': 'error',
            // 禁止不安全的成员访问
            '@typescript-eslint/no-unsafe-member-access': 'error',
            // 禁止不安全的返回值
            '@typescript-eslint/no-unsafe-return': 'error',
            // 要求 Promise 必须被处理
            '@typescript-eslint/no-floating-promises': 'error',
            // 禁止 await 非 thenable 的值
            '@typescript-eslint/await-thenable': 'error',
            // 禁止冗余的类型断言
            '@typescript-eslint/no-unnecessary-type-assertion': 'error',
            // 禁止冗余的条件判断
            '@typescript-eslint/no-unnecessary-condition': 'warn',
            // 要求函数有明确的返回类型
            '@typescript-eslint/explicit-function-return-type': [
                'warn',
                {
                    allowExpressions: true,
                    allowHigherOrderFunctions: true,
                    allowTypedFunctionExpressions: true,
                },
            ],

            // ====================== 最佳实践规则 ======================
            // 强制使用类型导入
            '@typescript-eslint/consistent-type-imports': [
                'error',
                { prefer: 'type-imports', disallowTypeAnnotations: false },
            ],
            // 强制使用 interface 定义对象类型
            '@typescript-eslint/consistent-type-definitions': ['error', 'interface'],
            // 强制使用空值合并运算符代替逻辑或
            '@typescript-eslint/prefer-nullish-coalescing': 'error',
            // 强制使用可选链运算符
            '@typescript-eslint/prefer-optional-chain': 'error',
            // 强制使用 for-of 循环代替 for 循环
            '@typescript-eslint/prefer-for-of': 'error',
            // 禁止不必要的类型参数
            '@typescript-eslint/no-unnecessary-type-arguments': 'error',
            // 禁止不必要的类型约束
            '@typescript-eslint/no-unnecessary-type-constraint': 'error',

            // ====================== 代码风格规则 ======================
            // 强制使用单引号
            quotes: ['error', 'single', { avoidEscape: true }],
            // 强制使用分号
            semi: ['error', 'always'],
            // 4空格缩进
            indent: ['error', 4, { SwitchCase: 1 }],
            // 禁止 console 输出 (除了 warn 和 error)
            'no-console': ['error', { allow: ['warn', 'error'] }],
            // 强制使用 === 和 !==
            eqeqeq: ['error', 'always'],
            // 强制使用大括号
            curly: 'error',
            // 禁止多个空格
            'no-multi-spaces': 'error',

            // ====================== 其他重要规则 ======================
            // 禁止未使用的变量 (TypeScript 增强版)
            '@typescript-eslint/no-unused-vars': [
                'warn',
                {
                    argsIgnorePattern: '^_',
                    varsIgnorePattern: '^_',
                    ignoreRestSiblings: true,
                },
            ],
            // 禁止空块语句
            'no-empty': ['error', { allowEmptyCatch: true }],
            // 禁止冗余的类型声明
            '@typescript-eslint/no-inferrable-types': 'error',
            // 强制数组类型使用泛型语法
            '@typescript-eslint/array-type': ['error', { default: 'generic' }],
            // 强制方法签名风格
            '@typescript-eslint/method-signature-style': ['error', 'property'],
        },
    },
]);
