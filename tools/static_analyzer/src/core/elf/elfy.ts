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
 * @file elfy.ts
 * @description
 * A comprehensive TypeScript parser for ELF (Executable and Linkable Format) files.
 * This parser is designed to extract and interpret various components of ELF binaries, including:
 * - **ELF Headers:** Parses the main ELF header to determine class, endianness, type, machine architecture, entry point, and more.
 * - **Program Headers:** Analyzes program headers to identify loadable segments, dynamic linking information, and other executable sections.
 * - **Section Headers:** Extracts section headers to access different sections like `.text`, `.data`, `.symtab`, `.dynsym`, `.plt`, etc.
 * - **Symbols:** Retrieves and parses symbols from both `.dynsym` and `.symtab` sections, providing details such as name, type, binding, visibility, and associated sections.
 * - **Procedure Linkage Table (PLT) Entries:** Identifies PLT entries and maps them to their corresponding symbols, facilitating the analysis of external function calls.
 *
 * This TypeScript version is a translation and enhancement of the original JavaScript implementation `elfy.js` by **Gang Fan**.
 * Additional functionalities have been incorporated to improve symbol resolution and PLT mapping, ensuring accurate and efficient ELF file analysis.
 *
 * ## Features
 * - **64-bit and 32-bit ELF Support:** Automatically detects and parses both 64-bit and 32-bit ELF binaries, handling endianness and architecture-specific nuances.
 * - **Robust Error Handling:** Provides informative error messages and warnings to assist in debugging and ensuring the integrity of parsed data.
 * - **Extensible Design:** Structured to allow easy addition of support for more ELF sections, architectures, and parsing features in the future.
 * - **Debugging and Logging:** Includes debugging statements to trace the parsing process and verify the correctness of symbol and PLT mappings.
 *
 * ## Author
 * **Gang Fan**
 *
 * ## Version
 * `1.0.0`
 *
 * ## Usage
 * ```typescript
 * import { parseELF, ParsedSymbol, PLTEntry } from './elfy';
 * import * as fs from 'fs';
 * import * as path from 'path';
 *
 * const elfPath = path.resolve(__dirname, 'libc.so'); // Replace with your ELF file path
 * const elfBuffer = fs.readFileSync(elfPath);
 *
 * try {
 *   const elf = parseELF(elfBuffer);
 *   console.log('ELF Header:', elf);
 *
 *   // Access Symbols
 *   if (elf.body.symbols) {
 *     console.log('Dynamic Symbols:', elf.body.symbols);
 *   }
 *
 *   if (elf.body.symtabSymbols) {
 *     console.log('Symtab Symbols:', elf.body.symtabSymbols);
 *   }
 *
 *   // Access PLT Entries
 *   if (elf.body.plt) {
 *     console.log('PLT Entries:', elf.body.plt);
 *   }
 *
 * } catch (error) {
 *   console.error('Failed to parse ELF file:', error);
 * }
 * ```
 *
 * ## Dependencies
 * - **Node.js Buffer Module:** Utilized for handling binary data.
 * - **Assert Module:** Used for validating assumptions during parsing.
 *
 * ## Notes
 * - Ensure that the ELF file provided is valid and accessible.
 * - The parser currently assumes a default PLT entry size of 16 bytes, which is common for architectures like x86-64. Adjustments may be necessary for other architectures.
 * - Reserved PLT entries (commonly the first one or two entries) are accounted for to prevent out-of-bounds access during PLT parsing.
 *
 */

import * as assert from 'assert';
import type { Buffer } from 'buffer';
import { Logger, LOG_MODULE_TYPE } from 'arkanalyzer';
const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

/**
 * Enums for various constants to improve type safety
 */

enum ELFClassEnum {
    NONE = 0,
    ELF32 = 1,
    ELF64 = 2,
    NUM = 3,
}

enum EndianEnum {
    NONE = 0,
    LSB = 1,
    MSB = 2,
    NUM = 3,
}

enum ELFOSABIEnum {
    SYSV = 0,
    HPUX = 1,
    NETBSD = 2,
    LINUX = 3,
    UNKNOWN4 = 4,
    UNKNOWN5 = 5,
    SOLARIS = 6,
    AIX = 7,
    IRIX = 8,
    FREEBSD = 9,
    TRU64 = 10,
    MODESTO = 11,
    OPENBSD = 12,
    OPENVMS = 13,
    NSK = 14,
    AROS = 15,
    ARM = 97,
    STANDALONE = 255,
}

enum ELFTypeEnum {
    NONE = 0,
    REL = 1,
    EXEC = 2,
    DYN = 3,
    CORE = 4,
    NUM = 5,
}

enum MachineEnum {
    NONE = 0,
    M32 = 1,
    SPARC = 2,
    _386 = 3,
    _68K = 4,
    _88K = 5,
    _486 = 6,
    _860 = 7,
    MIPS = 8,
    S370 = 9,
    MIPS_RS3_LE = 10,
    RS6000 = 11,
    UNKNOWN12 = 12,
    UNKNOWN13 = 13,
    UNKNOWN14 = 14,
    PA_RISC = 15,
    NCUBE = 16,
    VPP500 = 17,
    SPARC32PLUS = 18,
    _960 = 19,
    PPC = 20,
    PPC64 = 21,
    S390 = 22,
    UNKNOWN23 = 23,
    UNKNOWN24 = 24,
    UNKNOWN25 = 25,
    UNKNOWN26 = 26,
    UNKNOWN27 = 27,
    UNKNOWN28 = 28,
    UNKNOWN29 = 29,
    UNKNOWN30 = 30,
    UNKNOWN31 = 31,
    UNKNOWN32 = 32,
    UNKNOWN33 = 33,
    UNKNOWN34 = 34,
    UNKNOWN35 = 35,
    V800 = 36,
    FR20 = 37,
    RH32 = 38,
    RCE = 39,
    ARM = 40,
    ALPHA = 41,
    SH = 42,
    SPARCV9 = 43,
    TRICORE = 44,
    ARC = 45,
    H8_300 = 46,
    H8_300H = 47,
    H8S = 48,
    H8_500 = 49,
    IA_64 = 50,
    MIPS_X = 51,
    COLDFIRE = 52,
    _68HC12 = 53,
    MMA = 54,
    PCP = 55,
    NCPU = 56,
    NDR1 = 57,
    STARCORE = 58,
    ME16 = 59,
    ST100 = 60,
    TINYJ = 61,
    AMD64 = 62,
    PDSP = 63,
    UNKNOWN64 = 64,
    UNKNOWN65 = 65,
    FX66 = 66,
    ST9PLUS = 67,
    ST7 = 68,
    _68HC16 = 69,
    _68HC11 = 70,
    _68HC08 = 71,
    _68HC05 = 72,
    SVX = 73,
    ST19 = 74,
    VAX = 75,
    CRIS = 76,
    JAVELIN = 77,
    FIREPATH = 78,
    ZSP = 79,
    MMIX = 80,
    HUANY = 81,
    PRISM = 82,
    AVR = 83,
    FR30 = 84,
    D10V = 85,
    D30V = 86,
    V850 = 87,
    M32R = 88,
    MN10300 = 89,
    MN10200 = 90,
    PJ = 91,
    OPENRISC = 92,
    ARC_A5 = 93,
    XTENSA = 94,
    NUM = 95,
    AARCH64 = 183,
}

enum SectionTypeEnum {
    NULL = 0,
    PROGBITS = 1,
    SYMTAB = 2,
    STRTAB = 3,
    RELA = 4,
    HASH = 5,
    DYNAMIC = 6,
    NOTE = 7,
    NOBITS = 8,
    REL = 9,
    SHLIB = 10,
    DYNSYM = 11,
    UNKNOWN12 = 12,
    UNKNOWN13 = 13,
    INIT_ARRAY = 14,
    FINI_ARRAY = 15,
    PREINIT_ARRAY = 16,
    GROUP = 17,
    SYMTAB_SHNDX = 18,
    NUM = 19,
    LOOS = 0x60000000,
    SUNW_CAPCHAIN = 0x6fffffef,
    SUNW_CAPINFO = 0x6ffffff0,
    SUNW_SYMSORT = 0x6ffffff1,
    SUNW_TLSSORT = 0x6ffffff2,
    SUNW_LDYNSYM = 0x6ffffff3,
    SUNW_DOF = 0x6ffffff4,
    GNU_ATTRIBUTES = 0x6ffffff5,
    GNU_HASH = 0x6ffffff6,
    GNU_LIBLIST = 0x6ffffff7,
    CHECKSUM = 0x6ffffff8,
    SUNW_DEBUG = 0x6ffffff9,
    SUNW_MOVE = 0x6ffffffa,
    SUNW_COMDAT = 0x6ffffffb,
    SUNW_SYMINFO = 0x6ffffffc,
    SUNW_VERDEF = 0x6ffffffd,
    SUNW_VERNEED = 0x6ffffffe,
    HIOS = 0x6fffffff,
}

enum SymbolTypeEnum {
    NOTYPE = 0,
    OBJECT = 1,
    FUNC = 2,
    SECTION = 3,
    FILE = 4,
    COMMON = 5,
    TLS = 6,
    LOPROC = 10,
    HIPROC = 12,
}

enum SymbolBindingEnum {
    LOCAL = 0,
    GLOBAL = 1,
    WEAK = 2,
    LOPROC = 10,
    HIPROC = 12,
}

enum SymbolVisibilityEnum {
    DEFAULT = 0,
    INTERNAL = 1,
    HIDDEN = 2,
    PROTECTED = 3,
}

/**
 * Constants used in ELF parsing
 */
const constants = {
    class: {
        [ELFClassEnum.NONE]: 'none',
        [ELFClassEnum.ELF32]: '32',
        [ELFClassEnum.ELF64]: '64',
        [ELFClassEnum.NUM]: 'num',
    } as Record<number, string>,

    endian: {
        [EndianEnum.NONE]: 'none',
        [EndianEnum.LSB]: 'lsb',
        [EndianEnum.MSB]: 'msb',
        [EndianEnum.NUM]: 'num',
    } as Record<number, string>,

    version: {
        [1]: 'current', // Version 1 is the current version
        [2]: 'num',
    } as Record<number, string>,

    osabi: {
        [ELFOSABIEnum.SYSV]: 'sysv',
        [ELFOSABIEnum.HPUX]: 'hpux',
        [ELFOSABIEnum.NETBSD]: 'netbsd',
        [ELFOSABIEnum.LINUX]: 'linux',
        [ELFOSABIEnum.UNKNOWN4]: 'unknown4',
        [ELFOSABIEnum.UNKNOWN5]: 'unknown5',
        [ELFOSABIEnum.SOLARIS]: 'solaris',
        [ELFOSABIEnum.AIX]: 'aix',
        [ELFOSABIEnum.IRIX]: 'irix',
        [ELFOSABIEnum.FREEBSD]: 'freebsd',
        [ELFOSABIEnum.TRU64]: 'tru64',
        [ELFOSABIEnum.MODESTO]: 'modesto',
        [ELFOSABIEnum.OPENBSD]: 'openbsd',
        [ELFOSABIEnum.OPENVMS]: 'openvms',
        [ELFOSABIEnum.NSK]: 'nsk',
        [ELFOSABIEnum.AROS]: 'aros',
        [ELFOSABIEnum.ARM]: 'arm',
        [ELFOSABIEnum.STANDALONE]: 'standalone',
    } as Record<number, string>,

    abiversion: {
        [0]: 'none',
        [1]: 'current',
        [2]: 'num',
    } as Record<number, string>,

    machine: {
        [MachineEnum.NONE]: 'none',
        [MachineEnum.M32]: 'm32',
        [MachineEnum.SPARC]: 'sparc',
        [MachineEnum._386]: '386',
        [MachineEnum._68K]: '68k',
        [MachineEnum._88K]: '88k',
        [MachineEnum._486]: '486',
        [MachineEnum._860]: '860',
        [MachineEnum.MIPS]: 'mips',
        [MachineEnum.S370]: 's370',
        [MachineEnum.MIPS_RS3_LE]: 'mips_rs3_le',
        [MachineEnum.RS6000]: 'rs6000',
        [MachineEnum.UNKNOWN12]: 'unknown12',
        [MachineEnum.UNKNOWN13]: 'unknown13',
        [MachineEnum.UNKNOWN14]: 'unknown14',
        [MachineEnum.PA_RISC]: 'pa_risc',
        [MachineEnum.NCUBE]: 'ncube',
        [MachineEnum.VPP500]: 'vpp500',
        [MachineEnum.SPARC32PLUS]: 'sparc32plus',
        [MachineEnum._960]: '960',
        [MachineEnum.PPC]: 'ppc',
        [MachineEnum.PPC64]: 'ppc64',
        [MachineEnum.S390]: 's390',
        [MachineEnum.UNKNOWN23]: 'unknown23',
        [MachineEnum.UNKNOWN24]: 'unknown24',
        [MachineEnum.UNKNOWN25]: 'unknown25',
        [MachineEnum.UNKNOWN26]: 'unknown26',
        [MachineEnum.UNKNOWN27]: 'unknown27',
        [MachineEnum.UNKNOWN28]: 'unknown28',
        [MachineEnum.UNKNOWN29]: 'unknown29',
        [MachineEnum.UNKNOWN30]: 'unknown30',
        [MachineEnum.UNKNOWN31]: 'unknown31',
        [MachineEnum.UNKNOWN32]: 'unknown32',
        [MachineEnum.UNKNOWN33]: 'unknown33',
        [MachineEnum.UNKNOWN34]: 'unknown34',
        [MachineEnum.UNKNOWN35]: 'unknown35',
        [MachineEnum.V800]: 'v800',
        [MachineEnum.FR20]: 'fr20',
        [MachineEnum.RH32]: 'rh32',
        [MachineEnum.RCE]: 'rce',
        [MachineEnum.ARM]: 'arm',
        [MachineEnum.ALPHA]: 'alpha',
        [MachineEnum.SH]: 'sh',
        [MachineEnum.SPARCV9]: 'sparcv9',
        [MachineEnum.TRICORE]: 'tricore',
        [MachineEnum.ARC]: 'arc',
        [MachineEnum.H8_300]: 'h8_300',
        [MachineEnum.H8_300H]: 'h8_300h',
        [MachineEnum.H8S]: 'h8s',
        [MachineEnum.H8_500]: 'h8_500',
        [MachineEnum.IA_64]: 'ia_64',
        [MachineEnum.MIPS_X]: 'mips_x',
        [MachineEnum.COLDFIRE]: 'coldfire',
        [MachineEnum._68HC12]: '68hc12',
        [MachineEnum.MMA]: 'mma',
        [MachineEnum.PCP]: 'pcp',
        [MachineEnum.NCPU]: 'ncpu',
        [MachineEnum.NDR1]: 'ndr1',
        [MachineEnum.STARCORE]: 'starcore',
        [MachineEnum.ME16]: 'me16',
        [MachineEnum.ST100]: 'st100',
        [MachineEnum.TINYJ]: 'tinyj',
        [MachineEnum.AMD64]: 'amd64',
        [MachineEnum.PDSP]: 'pdsp',
        [MachineEnum.UNKNOWN64]: 'unknown64',
        [MachineEnum.UNKNOWN65]: 'unknown65',
        [MachineEnum.FX66]: 'fx66',
        [MachineEnum.ST9PLUS]: 'st9plus',
        [MachineEnum.ST7]: 'st7',
        [MachineEnum._68HC16]: '68hc16',
        [MachineEnum._68HC11]: '68hc11',
        [MachineEnum._68HC08]: '68hc08',
        [MachineEnum._68HC05]: '68hc05',
        [MachineEnum.SVX]: 'svx',
        [MachineEnum.ST19]: 'st19',
        [MachineEnum.VAX]: 'vax',
        [MachineEnum.CRIS]: 'cris',
        [MachineEnum.JAVELIN]: 'javelin',
        [MachineEnum.FIREPATH]: 'firepath',
        [MachineEnum.ZSP]: 'zsp',
        [MachineEnum.MMIX]: 'mmix',
        [MachineEnum.HUANY]: 'huany',
        [MachineEnum.PRISM]: 'prism',
        [MachineEnum.AVR]: 'avr',
        [MachineEnum.FR30]: 'fr30',
        [MachineEnum.D10V]: 'd10v',
        [MachineEnum.D30V]: 'd30v',
        [MachineEnum.V850]: 'v850',
        [MachineEnum.M32R]: 'm32r',
        [MachineEnum.MN10300]: 'mn10300',
        [MachineEnum.MN10200]: 'mn10200',
        [MachineEnum.PJ]: 'pj',
        [MachineEnum.OPENRISC]: 'openrisc',
        [MachineEnum.ARC_A5]: 'arc_a5',
        [MachineEnum.XTENSA]: 'xtensa',
        [MachineEnum.NUM]: 'num',
        [MachineEnum.AARCH64]: 'AArch64',
    } as Record<number, string>,

    type: {
        [ELFTypeEnum.NONE]: 'none',
        [ELFTypeEnum.REL]: 'rel',
        [ELFTypeEnum.EXEC]: 'exec',
        [ELFTypeEnum.DYN]: 'dyn',
        [ELFTypeEnum.CORE]: 'core',
        [ELFTypeEnum.NUM]: 'num',
    } as Record<number, string>,

    entryType: {
        [0]: 'null',
        [1]: 'load',
        [2]: 'dynamic',
        [3]: 'interp',
        [4]: 'note',
        [5]: 'shlib',
        [6]: 'phdr',
        [7]: 'tls',

        [0x6464e550]: 'sunw_unwind',
        [0x6474e550]: 'gnu_eh_frame',
        [0x6474e551]: 'gnu_stack',
        [0x6474e552]: 'gnu_relro',

        [0x6ffffffa]: 'sunwbss',
        [0x6ffffffb]: 'sunwstack',
        [0x6ffffffc]: 'sunwdtrace',
        [0x6ffffffd]: 'sunwcap',
    } as Record<number, string>,

    entryFlags: {
        [4]: 'r',
        [2]: 'w',
        [1]: 'x',
        [0x00100000]: 'sunw_failure',
        [0x00200000]: 'sunw_killed',
        [0x00400000]: 'sunw_siginfo',
    } as Record<number, string>,

    sectType: {
        [SectionTypeEnum.NULL]: 'null', // Overridden from 'undef'
        [SectionTypeEnum.PROGBITS]: 'progbits',
        [SectionTypeEnum.SYMTAB]: 'symtab',
        [SectionTypeEnum.STRTAB]: 'strtab',
        [SectionTypeEnum.RELA]: 'rela',
        [SectionTypeEnum.HASH]: 'hash',
        [SectionTypeEnum.DYNAMIC]: 'dynamic',
        [SectionTypeEnum.NOTE]: 'note',
        [SectionTypeEnum.NOBITS]: 'nobits',
        [SectionTypeEnum.REL]: 'rel',
        [SectionTypeEnum.SHLIB]: 'shlib',
        [SectionTypeEnum.DYNSYM]: 'dynsym',
        [SectionTypeEnum.UNKNOWN12]: 'unknown12',
        [SectionTypeEnum.UNKNOWN13]: 'unknown13',
        [SectionTypeEnum.INIT_ARRAY]: 'init_array',
        [SectionTypeEnum.FINI_ARRAY]: 'fini_array',
        [SectionTypeEnum.PREINIT_ARRAY]: 'preinit_array',
        [SectionTypeEnum.GROUP]: 'group',
        [SectionTypeEnum.SYMTAB_SHNDX]: 'symtab_shndx',
        [SectionTypeEnum.NUM]: 'num',
        [SectionTypeEnum.LOOS]: 'loos',
        [SectionTypeEnum.SUNW_CAPCHAIN]: 'sunw_capchain',
        [SectionTypeEnum.SUNW_CAPINFO]: 'sunw_capinfo',
        [SectionTypeEnum.SUNW_SYMSORT]: 'sunw_symsort',
        [SectionTypeEnum.SUNW_TLSSORT]: 'sunw_tlsort',
        [SectionTypeEnum.SUNW_LDYNSYM]: 'sunw_ldynsym',
        [SectionTypeEnum.SUNW_DOF]: 'sunw_dof',
        [SectionTypeEnum.GNU_ATTRIBUTES]: 'gnu_attributes',
        [SectionTypeEnum.GNU_HASH]: 'gnu_hash',
        [SectionTypeEnum.GNU_LIBLIST]: 'gnu_liblist',
        [SectionTypeEnum.CHECKSUM]: 'checksum',
        [SectionTypeEnum.SUNW_DEBUG]: 'sunw_debug',
        [SectionTypeEnum.SUNW_MOVE]: 'sunw_move',
        [SectionTypeEnum.SUNW_COMDAT]: 'sunw_comdat',
        [SectionTypeEnum.SUNW_SYMINFO]: 'sunw_syminfo',
        [SectionTypeEnum.SUNW_VERDEF]: 'sunw_verdef',
        [SectionTypeEnum.SUNW_VERNEED]: 'sunw_verneed',
        [SectionTypeEnum.HIOS]: 'hios',
    } as Record<number, string>,

    sectFlags: {
        [0x01]: 'write',
        [0x02]: 'alloc',
        [0x04]: 'execinstr',
        [0x10]: 'merge',
        [0x20]: 'strings',
        [0x40]: 'info_link',
        [0x80]: 'link_order',
        [0x100]: 'os_nonconforming',
        [0x200]: 'group',
        [0x400]: 'tls',
    } as Record<number, string>,
} as const;

/**
 * Type Definitions
 */
interface ELFHeader {
    class: string;
    endian: string;
    elfVersion: string;
    osabi: string;
    abiversion: string;
    type: string;
    machine: string;
    entry: bigint | number;
    phoff: bigint | number;
    shoff: bigint | number;
    flags: number;
    ehsize: number;
    phentsize: number;
    phnum: number;
    shentsize: number;
    shnum: number;
    shstrndx: number;
}

interface ELFProgram {
    type: string;
    offset: bigint | number;
    vaddr: bigint | number;
    paddr: bigint | number;
    filesz: bigint | number;
    memsz: bigint | number;
    flags: Record<string, boolean>;
    align: bigint | number;
    data: Buffer;
}

interface ELFSection {
    name: string;
    type: string;
    flags: Record<string, boolean>;
    addr: bigint | number;
    off: bigint | number;
    size: bigint | number;
    link: number;
    info: number;
    addralign: bigint | number;
    entsize: bigint | number;
    data: Buffer;
    nameoffset: number;
}

// Define interfaces for symbol entries
interface Elf32_Sym {
    st_name: number;
    st_value: number;
    st_size: number;
    st_info: number;
    st_other: number;
    st_shndx: number;
}

interface Elf64_Sym {
    st_name: number;
    st_info: number;
    st_other: number;
    st_shndx: number;
    st_value: bigint;
    st_size: bigint;
}

type Elf_Sym = Elf32_Sym | Elf64_Sym;

export interface ParsedSymbol {
    name: string;
    value: bigint | number;
    size: bigint | number;
    type: string;
    binding: string;
    visibility: string;
    section: string;
}

export interface PLTEntry {
    index: number; // PLT entry index
    address: bigint | number; // Address of the PLT entry
    symbol: string; // Corresponding symbol name
}

// Relocation Entry Interfaces
interface Elf32_Rela {
    r_offset: number;
    r_info: number;
    r_addend: number;
}

interface Elf64_Rela {
    r_offset: bigint;
    r_info: bigint;
    r_addend: bigint;
}

type Elf_Rela = Elf32_Rela | Elf64_Rela;

export interface ParsedRelocation {
    offset: bigint | number;
    symbol: string;
    type: string;
    addend: bigint | number;
}

interface ELFBody {
    programs: Array<ELFProgram>;
    sections: Array<ELFSection>;
    symbols?: Array<ParsedSymbol>; // .dynsym
    symtabSymbols?: Array<ParsedSymbol>; // .symtab
    plt?: Array<PLTEntry>; // PLT entries
}

export interface ELF extends ELFHeader {
    body: ELFBody;
}

/**
 * Parser Class
 */
class Parser {
    private endian: 'little' | 'big' = 'little';
    private is64 = false;

    private bufferSections?: Array<ELFSection>;

    constructor() {}

    /**
     * Map flags based on a mapping object
     */
    private mapFlags(value: number, map: Record<number, string>): Record<string, boolean> {
        const res: Record<string, boolean> = {};

        for (let bit = 1; (value < 0 || bit <= value) && bit !== 0; bit <<= 1) {
            if (value & bit) {
                res[map[bit] || bit.toString()] = true;
            }
        }

        return res;
    }

    /**
     * Execute parsing on the provided buffer
     */
    public execute(buf: Buffer): ELF {
        if (buf.length < 16) {
            throw new Error('Not enough bytes to parse ident');
        }

        const magic = buf.slice(0, 4).toString('binary');
        if (magic !== '\x7fELF') {
            throw new Error('Invalid magic: ' + magic);
        }

        const header = this.parseHeader(buf);
        const body = this.parseBody(buf, header);
        const resolvedBody = this.resolveBody(body, header);

        // Store sections for getSectionName
        this.bufferSections = resolvedBody.sections;

        // Ensure body is present
        return { ...header, body: resolvedBody };
    }

    /**
     * Parse the ELF header
     */
    private parseHeader(buf: Buffer): ELFHeader {
        const classByte = buf[4];
        const class_ = constants.class[classByte] || 'unknown';

        const endianByte = buf[5];
        const endian = constants.endian[endianByte] || 'unknown';

        const elfVersionByte = buf[6];
        const elfVersion = constants.version[elfVersionByte] || 'unknown';

        const osabiByte = buf[7];
        const osabi = constants.osabi[osabiByte] || 'unknown';

        const abiversionByte = buf[8];
        const abiversion = constants.abiversion[abiversionByte] || 'unknown';

        if (class_ !== '32' && class_ !== '64') {
            throw new Error('Invalid class: ' + class_);
        }

        if (endian !== 'lsb' && endian !== 'msb') {
            throw new Error('Invalid endian: ' + endian);
        }

        this.endian = endian === 'lsb' ? 'little' : 'big';
        this.is64 = class_ === '64';

        let type: string;
        let machine: string;
        let entry: bigint | number;
        let phoff: bigint | number;
        let shoff: bigint | number;
        let flags: number;
        let ehsize: number;
        let phentsize: number;
        let phnum: number;
        let shentsize: number;
        let shnum: number;
        let shstrndx: number;

        if (!this.is64) {
            type = constants.type[this.readUInt16(buf, 16)] || 'unknown';
            machine = constants.machine[this.readUInt16(buf, 18)] || 'unknown';
            entry = this.readUInt32(buf, 24);
            phoff = this.readUInt32(buf, 28);
            shoff = this.readUInt32(buf, 32);
            flags = this.readUInt32(buf, 36);
            ehsize = this.readUInt16(buf, 40);
            phentsize = this.readUInt16(buf, 42);
            phnum = this.readUInt16(buf, 44);
            shentsize = this.readUInt16(buf, 46);
            shnum = this.readUInt16(buf, 48);
            shstrndx = this.readUInt16(buf, 50);
        } else {
            type = constants.type[this.readUInt16(buf, 16)] || 'unknown';
            machine = constants.machine[this.readUInt16(buf, 18)] || 'unknown';
            entry = this.readUInt64(buf, 24);
            phoff = this.readUInt64(buf, 32);
            shoff = this.readUInt64(buf, 40);
            flags = this.readUInt32(buf, 48);
            ehsize = this.readUInt16(buf, 52);
            phentsize = this.readUInt16(buf, 54);
            phnum = this.readUInt16(buf, 56);
            shentsize = this.readUInt16(buf, 58);
            shnum = this.readUInt16(buf, 60);
            shstrndx = this.readUInt16(buf, 62);
        }

        return {
            class: class_,
            endian: endian,
            elfVersion: elfVersion,
            osabi: osabi,
            abiversion: abiversion,
            type: type,
            machine: machine,
            entry: entry,
            phoff: phoff,
            shoff: shoff,
            flags: flags,
            ehsize: ehsize,
            phentsize: phentsize,
            phnum: phnum,
            shentsize: shentsize,
            shnum: shnum,
            shstrndx: shstrndx,
        };
    }

    /**
     * Parse the ELF body (programs and sections)
     */
    private parseBody(buf: Buffer, header: ELFHeader): ELFBody {
        return {
            programs: this.parsePrograms(buf, header),
            sections: this.parseSections(buf, header),
        };
    }

    /**
     * Slice buffer into chunks
     */
    private sliceChunks(buf: Buffer, off: number | bigint, count: number, size: number): Array<Buffer> {
        const offset = typeof off === 'bigint' ? Number(off) : off;
        const start = offset;
        const end = start + count * size;
        if (end > buf.length) {
            throw new Error('Failed to slice chunks');
        }

        const chunks: Array<Buffer> = [];
        for (let current = start; current < end; current += size) {
            chunks.push(buf.slice(current, current + size));
        }

        return chunks;
    }

    /**
     * Parse program headers
     */
    private parsePrograms(buf: Buffer, header: ELFHeader): Array<ELFProgram> {
        if (header.phoff === 0 || header.phnum === 0) {
            return [];
        }

        const programs = this.sliceChunks(buf, header.phoff, header.phnum, header.phentsize);

        return programs.map((program) => this.parseProgram(program, header, buf));
    }

    /**
     * Parse a single program header
     */
    private parseProgram(ent: Buffer, header: ELFHeader, buf: Buffer): ELFProgram {
        const type = constants.entryType[this.readUInt32(ent, 0)] || 'unknown';

        let offset: bigint | number;
        let vaddr: bigint | number;
        let paddr: bigint | number;
        let filesz: bigint | number;
        let memsz: bigint | number;
        let flags: number;
        let align: bigint | number;

        if (!this.is64) {
            offset = this.readUInt32(ent, 4);
            vaddr = this.readUInt32(ent, 8);
            paddr = this.readUInt32(ent, 12);
            filesz = this.readUInt32(ent, 16);
            memsz = this.readUInt32(ent, 20);
            flags = this.readUInt32(ent, 24);
            align = this.readUInt32(ent, 28);
        } else {
            flags = this.readUInt32(ent, 4);
            offset = this.readUInt64(ent, 8);
            vaddr = this.readUInt64(ent, 16);
            paddr = this.readUInt64(ent, 24);
            filesz = this.readUInt64(ent, 32);
            memsz = this.readUInt64(ent, 40);
            align = this.readUInt64(ent, 48);
        }

        return {
            type: type,
            offset: offset,
            vaddr: vaddr,
            paddr: paddr,
            filesz: filesz,
            memsz: memsz,
            flags: this.mapFlags(flags, constants.entryFlags),
            align: align,
            data: buf.slice(Number(offset), Number(offset) + Number(filesz)),
        };
    }

    /**
     * Parse section headers
     */
    private parseSections(buf: Buffer, header: ELFHeader): Array<ELFSection> {
        if (header.shoff === 0 || header.shnum === 0) {
            return [];
        }

        const sections = this.sliceChunks(buf, header.shoff, header.shnum, header.shentsize);

        return sections.map((section) => this.parseSection(section, header, buf));
    }

    /**
     * Parse a single section header
     */
    private parseSection(section: Buffer, header: ELFHeader, buf: Buffer): ELFSection {
        const nameOffset = this.readUInt32(section, 0);
        const typeValue = this.readUInt32(section, 4);
        const type = constants.sectType[typeValue] || typeValue.toString();

        let flags: number;
        let addr: bigint | number;
        let off: bigint | number;
        let size: bigint | number;
        let link: number;
        let info: number;
        let addralign: bigint | number;
        let entsize: bigint | number;

        if (!this.is64) {
            flags = this.readUInt32(section, 8);
            addr = this.readUInt32(section, 12);
            off = this.readUInt32(section, 16);
            size = this.readUInt32(section, 20);
            link = this.readUInt32(section, 24);
            info = this.readUInt32(section, 28);
            addralign = this.readUInt32(section, 32);
            entsize = this.readUInt32(section, 36);
        } else {
            flags = Number(this.readUInt64(section, 8));
            addr = this.readUInt64(section, 16);
            off = this.readUInt64(section, 24);
            size = this.readUInt64(section, 32);
            link = this.readUInt32(section, 40);
            info = this.readUInt32(section, 44);
            addralign = this.readUInt64(section, 48);
            entsize = this.readUInt64(section, 56);
        }

        return {
            name: '', // To be resolved later
            type: type,
            flags: this.mapFlags(flags, constants.sectFlags),
            addr: addr,
            off: off,
            size: size,
            link: link,
            info: info,
            addralign: addralign,
            entsize: entsize,
            data: buf.slice(Number(off), Number(off) + Number(size)),
            nameoffset: nameOffset,
        };
    }

    /**
     * Resolve section names using the section header string table
     */
    private resolveBody(body: ELFBody, header: ELFHeader): ELFBody {
        const strSection = body.sections[header.shstrndx];
        assert.strictEqual(strSection.type, 'strtab', 'Expected shstrtab section');

        return {
            programs: body.programs,
            sections: body.sections.map((section) => {
                section.name = this.resolveStr(strSection.data, section.nameoffset as unknown as number);
                return section;
            }),
        };
    }

    /**
     * Resolve a string from the string table
     */
    private resolveStr(strtab: Buffer, off: number): string {
        let end = off;
        while (end < strtab.length && strtab[end] !== 0) {
            end++;
        }
        return strtab.slice(off, end).toString('utf8');
    }

    /**
     * Read unsigned 16-bit integer with correct endianness
     */
    private readUInt16(buf: Buffer, offset: number): number {
        return this.endian === 'little' ? buf.readUInt16LE(offset) : buf.readUInt16BE(offset);
    }

    /**
     * Read unsigned 32-bit integer with correct endianness
     */
    private readUInt32(buf: Buffer, offset: number): number {
        return this.endian === 'little' ? buf.readUInt32LE(offset) : buf.readUInt32BE(offset);
    }

    /**
     * Read unsigned 64-bit integer with correct endianness
     */
    private readUInt64(buf: Buffer, offset: number): bigint {
        return this.endian === 'little' ? buf.readBigUInt64LE(offset) : buf.readBigUInt64BE(offset);
    }

    /**
     * Parse the .dynsym section and return an array of ParsedSymbol
     */
    public parseDynSym(section: ELFSection, stringTable: ELFSection): Array<ParsedSymbol> {
        const symbols: Array<ParsedSymbol> = [];
        const buf = section.data;
        const is64 = this.is64;
        const symSize = is64 ? 24 : 16; // Size of each symbol entry

        const numSymbols = Math.floor(buf.length / symSize);
        for (let i = 0; i < numSymbols; i++) {
            const offset = i * symSize;
            let sym: Elf_Sym;

            if (is64) {
                sym = {
                    st_name: this.readUInt32(buf, offset),
                    st_info: buf[offset + 4],
                    st_other: buf[offset + 5],
                    st_shndx: this.readUInt16(buf, offset + 6),
                    st_value: this.readUInt64(buf, offset + 8),
                    st_size: this.readUInt64(buf, offset + 16),
                } as Elf64_Sym;
            } else {
                sym = {
                    st_name: this.readUInt32(buf, offset),
                    st_value: this.readUInt32(buf, offset + 4),
                    st_size: this.readUInt32(buf, offset + 8),
                    st_info: buf[offset + 12],
                    st_other: buf[offset + 13],
                    st_shndx: this.readUInt16(buf, offset + 14),
                } as Elf32_Sym;
            }

            // Parse st_info
            const binding = this.getSymbolBinding(sym.st_info);
            const type = this.getSymbolType(sym.st_info);
            const visibility = this.getSymbolVisibility(sym.st_other);
            const section = this.getSectionName(sym.st_shndx);

            // Resolve symbol name
            const name = this.resolveStr(stringTable.data, sym.st_name);

            // Debugging Statement
            logger.debug(`Symbol ${i}: name=${name}, type=${type}, binding=${binding}, section=${section}`);

            symbols.push({
                name,
                value: sym.st_value,
                size: sym.st_size,
                type,
                binding,
                visibility,
                section,
            });
        }

        return symbols;
    }

    /**
     * Get symbol binding from st_info
     */
    private getSymbolBinding(st_info: number): string {
        const binding = st_info >> 4;
        switch (binding) {
            case SymbolBindingEnum.LOCAL:
                return 'LOCAL';
            case SymbolBindingEnum.GLOBAL:
                return 'GLOBAL';
            case SymbolBindingEnum.WEAK:
                return 'WEAK';
            case SymbolBindingEnum.LOPROC:
                return 'LOPROC';
            case SymbolBindingEnum.HIPROC:
                return 'HIPROC';
            default:
                return 'UNKNOWN';
        }
    }

    /**
     * Get symbol type from st_info
     */
    private getSymbolType(st_info: number): string {
        const type = st_info & 0xf;
        switch (type) {
            case SymbolTypeEnum.NOTYPE:
                return 'NOTYPE';
            case SymbolTypeEnum.OBJECT:
                return 'OBJECT';
            case SymbolTypeEnum.FUNC:
                return 'FUNC';
            case SymbolTypeEnum.SECTION:
                return 'SECTION';
            case SymbolTypeEnum.FILE:
                return 'FILE';
            case SymbolTypeEnum.COMMON:
                return 'COMMON';
            case SymbolTypeEnum.TLS:
                return 'TLS';
            case SymbolTypeEnum.LOPROC:
                return 'LOPROC';
            case SymbolTypeEnum.HIPROC:
                return 'HIPROC';
            default:
                return 'UNKNOWN';
        }
    }

    /**
     * Get symbol visibility from st_other
     */
    private getSymbolVisibility(st_other: number): string {
        const visibility = st_other & 0x3;
        switch (visibility) {
            case SymbolVisibilityEnum.DEFAULT:
                return 'DEFAULT';
            case SymbolVisibilityEnum.INTERNAL:
                return 'INTERNAL';
            case SymbolVisibilityEnum.HIDDEN:
                return 'HIDDEN';
            case SymbolVisibilityEnum.PROTECTED:
                return 'PROTECTED';
            default:
                return 'UNKNOWN';
        }
    }

    /**
     * Get section name from section index
     */
    private getSectionName(st_shndx: number): string {
        if (st_shndx === 0) {
            return 'SHN_UNDEF';
        }

        if (st_shndx >= 0xff00 && st_shndx <= 0xffff) {
            // Processor-specific or OS-specific
            return `SHN_SPECIAL_${st_shndx}`;
        }

        // Retrieve the section from the ELF sections array
        const section = this.bufferSections?.[st_shndx];
        if (section) {
            // Assume that the name has already been resolved
            return section.name;
        }

        return `UNKNOWN_SECTION_${st_shndx}`;
    }

    /**
     * Parse the PLT section and return an array of PLTEntry
     */
    public parsePLT(
        pltSection: ELFSection,
        relaPltSection: ELFSection,
        symtab: ELFSection,
        stringTable: ELFSection
    ): Array<PLTEntry> {
        const pltEntries: Array<PLTEntry> = [];
        const buf = pltSection.data;

        // Determine PLT entry size based on architecture. Common sizes:
        // - x86: 16 bytes
        // - x86-64: 16 bytes
        // Adjust accordingly for other architectures.
        const pltEntrySize = 16; // Example for x86-64

        const numPltEntries = Math.floor(buf.length / pltEntrySize);

        // Parse relocation entries to map PLT indices to symbols
        const relocations = this.parseRelocationSection(relaPltSection, symtab, stringTable);

        // Determine the number of reserved PLT entries
        const reservedPltEntries = numPltEntries - relocations.length;

        // Typically, the first few PLT entries are reserved (e.g., PLT0, PLT1)
        // Adjust the starting index as needed. Here, we assume two reserved entries.
        // If reservedPltEntries is different, adjust accordingly.
        const expectedReservedEntries = 2; // Adjust based on your ELF file

        // Validate the expected number of reserved entries
        if (reservedPltEntries < expectedReservedEntries) {
            logger.warn(
                `Expected at least ${expectedReservedEntries} reserved PLT entries, but found ${reservedPltEntries}. Adjusting accordingly.`
            );
        }

        for (let i = expectedReservedEntries; i < numPltEntries; i++) {
            const pltOffset = i * pltEntrySize;
            const pltAddress = Number(pltSection.addr) + pltOffset;

            // Calculate the corresponding relocation index
            const relocationIndex = i - expectedReservedEntries;

            // Ensure we don't exceed the relocations array
            if (relocationIndex >= relocations.length) {
                logger.warn(`No corresponding relocation for PLT entry ${i} at address ${pltAddress}. Skipping.`);
                continue;
            }

            const relocation = relocations[relocationIndex];

            pltEntries.push({
                index: i,
                address: pltAddress,
                symbol: relocation.symbol,
            });
        }

        return pltEntries;
    }

    /**
     * Parse a relocation section (.rela.plt or .rel.plt) and return ParsedRelocation array
     */
    public parseRelocationSection(
        section: ELFSection,
        symtab: ELFSection,
        stringTable: ELFSection
    ): Array<ParsedRelocation> {
        const relocations: Array<ParsedRelocation> = [];
        const buf = section.data;
        const is64 = this.is64;
        const hasAddend = section.type === 'rela';
        const entrySize = is64 ? (hasAddend ? 24 : 16) : hasAddend ? 12 : 8;

        const numRelocations = Math.floor(buf.length / entrySize);
        for (let i = 0; i < numRelocations; i++) {
            let relocation: Elf_Rela;

            if (is64) {
                if (hasAddend) {
                    relocation = {
                        r_offset: this.readUInt64(buf, i * 24),
                        r_info: this.readUInt64(buf, i * 24 + 8),
                        r_addend: this.readUInt64(buf, i * 24 + 16),
                    } as Elf64_Rela;
                } else {
                    relocation = {
                        r_offset: this.readUInt64(buf, i * 16),
                        r_info: this.readUInt64(buf, i * 16 + 8),
                    } as Elf64_Rela; // Elf64_Rel doesn't have addend
                }
            } else {
                if (hasAddend) {
                    relocation = {
                        r_offset: this.readUInt32(buf, i * 12),
                        r_info: this.readUInt32(buf, i * 12 + 4),
                        r_addend: this.readUInt32(buf, i * 12 + 8),
                    } as Elf32_Rela;
                } else {
                    relocation = {
                        r_offset: this.readUInt32(buf, i * 8),
                        r_info: this.readUInt32(buf, i * 8 + 4),
                    } as Elf32_Rela; // Elf32_Rel doesn't have addend
                }
            }

            // Extract symbol index from r_info
            let symbolIndex: number;
            if (is64) {
                symbolIndex = Number(BigInt(relocation.r_info) >> 32n);
            } else {
                symbolIndex = Number(relocation.r_info) >> 8;
            }

            const symbol = this.getSymbolName(symtab, symbolIndex, stringTable);
            const type = this.getRelocationType(relocation.r_info, is64);

            const addend = hasAddend ? (is64 ? Number(relocation.r_addend) : relocation.r_addend) : 0; // Default addend to 0 if not present

            // Debugging Statements
            logger.debug(
                `Relocation ${i}: symbolIndex=${symbolIndex}, symbol=${symbol}, type=${type}, addend=${addend}`
            );

            relocations.push({
                offset: relocation.r_offset,
                symbol: symbol,
                type: type,
                addend: addend,
            });
        }

        return relocations;
    }

    /**
     * Get symbol name from symbol index
     */
    private getSymbolName(symtab: ELFSection, symbolIndex: number, stringTable: ELFSection): string {
        const is64 = this.is64;
        const symSize = is64 ? 24 : 16;
        const offset = symbolIndex * symSize;
        const buf = symtab.data;

        let st_name: number;
        if (is64) {
            st_name = this.readUInt32(buf, offset);
        } else {
            st_name = this.readUInt32(buf, offset);
        }

        return this.resolveStr(stringTable.data, st_name);
    }

    /**
     * Get relocation type from r_info
     */
    private getRelocationType(r_info: number | bigint, is64: boolean): string {
        // This is architecture-specific. For x86-64, use a mapping or return the numeric type.
        // For simplicity, we'll return the numeric type as a string.
        if (is64) {
            const type = Number(r_info) & 0xffffffff;
            return `R_X86_64_${type}`;
        } else {
            const type = Number(r_info) & 0xff;
            return `R_386_${type}`;
        }
    }

    /**
     * Get parsed symbols from the ELF object
     */
    public getSymbols(elf: ELF): Array<ParsedSymbol> {
        // Find the .dynsym section
        const dynsymSection = elf.body.sections.find((sec) => sec.name === '.dynsym' && sec.type === 'dynsym');

        if (!dynsymSection) {
            throw new Error('No .dynsym section found in ELF file');
        }

        // Find the associated string table (.dynstr)
        const dynstrSection = elf.body.sections.find((sec) => sec.name === '.dynstr' && sec.type === 'strtab');

        if (!dynstrSection) {
            throw new Error('No .dynstr section found in ELF file');
        }

        // Parse symbols
        const symbols = this.parseDynSym(dynsymSection, dynstrSection);
        return symbols;
    }

    /**
     * Get parsed symbols from the ELF object for .symtab
     */
    public getSymtabSymbols(elf: ELF): Array<ParsedSymbol> {
        // Find the .symtab section
        const symtabSection = elf.body.sections.find((sec) => sec.name === '.symtab' && sec.type === 'symtab');

        if (!symtabSection) {
            throw new Error('No .symtab section found in ELF file');
        }
        logger.warn('Found .dynsym section, may no strip this section');

        // Find the associated string table (.strtab)
        const strtabSection = elf.body.sections.find((sec) => sec.name === '.strtab' && sec.type === 'strtab');

        if (!strtabSection) {
            throw new Error('No .strtab section found in ELF file');
        }

        // Parse symbols
        const symbols = this.parseDynSym(symtabSection, strtabSection);
        return symbols;
    }

    /**
     * Get parsed PLT entries from the ELF object
     */
    public getPLT(elf: ELF): Array<PLTEntry> {
        // Find the .plt section
        const pltSection = elf.body.sections.find((sec) => sec.name === '.plt' && sec.type === 'progbits');

        if (!pltSection) {
            throw new Error('No .plt section found in ELF file');
        }

        // Find the corresponding relocation section (.rela.plt or .rel.plt)
        const relaPltSection =
            elf.body.sections.find((sec) => sec.name === '.rela.plt' && sec.type === 'rela') ??
            elf.body.sections.find((sec) => sec.name === '.rel.plt' && sec.type === 'rel');

        if (!relaPltSection) {
            throw new Error('No .rela.plt or .rel.plt section found in ELF file');
        }

        // Find the symbol table (.dynsym or .symtab)
        const symtabSection =
            elf.body.sections.find((sec) => sec.type === 'dynsym') ??
            elf.body.sections.find((sec) => sec.type === 'symtab');

        if (!symtabSection) {
            throw new Error('No .dynsym or .symtab section found in ELF file');
        }

        // Find the associated string table (.dynstr or .strtab)
        const stringTableSection =
            elf.body.sections.find((sec) => sec.name === '.dynstr' && sec.type === 'strtab') ??
            elf.body.sections.find((sec) => sec.name === '.strtab' && sec.type === 'strtab');

        if (!stringTableSection) {
            throw new Error('No .dynstr or .strtab section found in ELF file');
        }

        // Parse PLT entries
        const pltEntries = this.parsePLT(pltSection, relaPltSection, symtabSection, stringTableSection);

        return pltEntries;
    }
}

/**
 * Main parse function
 */
export function parseELF(buf: Buffer): ELF {
    const parser = new Parser();
    const elfHeader = parser.execute(buf);

    // Optionally parse .dynsym
    try {
        const symbols = parser.getSymbols(elfHeader);
        elfHeader.body.symbols = symbols;
    } catch (error) {
        // Handle cases where .dynsym or .dynstr might not exist
        logger.warn('Symbol parsing for .dynsym failed:', (error as Error).message);
    }

    // Optionally parse .symtab
    try {
        const symtabSymbols = parser.getSymtabSymbols(elfHeader);
        elfHeader.body.symtabSymbols = symtabSymbols;
    } catch (error) {
        // Handle cases where .symtab or .strtab might not exist
        logger.debug('Symbol parsing for .symtab failed:', (error as Error).message);
    }

    // Optionally parse PLT
    try {
        const pltEntries = parser.getPLT(elfHeader);
        elfHeader.body.plt = pltEntries;
    } catch (error) {
        // Handle cases where .plt or its relocation section might not exist
        logger.warn('PLT parsing failed:', (error as Error).message);
    }

    return elfHeader;
}
