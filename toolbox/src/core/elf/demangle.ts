/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Feasible solutions for C++ symbol demangling:
 * 1. c++filt command - requires the command to be pre-installed in the runtime environment
 * 2. Implement demangling in TS/JS according to the specification: https://itanium-cxx-abi.github.io/cxx-abi/abi.html#mangling
 * 3. Use Emscripten to compile the C++ API ___cxa_demangle into WebAssembly (wasm), providing a JavaScript callable interface.
 * __cxa_demangle is a GNU C++ symbol demangling function, typically used to convert C++ compiled symbol names into readable function signatures.
 *
 * This file adopts solution 3, the method for generating demangle-wasm file is as follows:
 * > touch demangle.cpp
 * > em++ -s EXPORTED_RUNTIME_METHODS='["UTF8ToString", "stringToUTF8"]' \
 *  -s EXPORTED_FUNCTIONS='["___cxa_demangle", "_malloc", "_free"]' \
 *  -s EXPORT_ALL=1 -s ENVIRONMENT=node -s MODULARIZE=1 -o demangle-wasm.js demangle.cpp
 */

interface DemangleModule {
    _malloc: (size: number) => number;
    _free: (ptr: number) => void;
    ___cxa_demangle: (mangled: number, output: number, length: number, status: number) => number;
    UTF8ToString: (ptr: number) => string;
    stringToUTF8: (str: string, ptr: number, maxBytes: number) => void;
    HEAP32: Int32Array;
}

type CreateModuleFunction = () => Promise<DemangleModule>;
const createModule: CreateModuleFunction = require('./demangle-wasm.js') as CreateModuleFunction;

export async function demangle(mangled: string): Promise<string> {
    const Module = await createModule();

    const ptr = Module._malloc(mangled.length + 1);
    Module.stringToUTF8(mangled, ptr, mangled.length + 1);

    const status = Module._malloc(4);
    Module.HEAP32[status >> 2] = 0;

    const demangledPtr = Module.___cxa_demangle(ptr, 0, 0, status);

    if (Module.HEAP32[status >> 2] === 0) {
        const result = Module.UTF8ToString(demangledPtr);
        Module._free(demangledPtr);
        Module._free(ptr);
        Module._free(status);
        return result;
    }

    Module._free(ptr);
    Module._free(status);
    return mangled;
}
