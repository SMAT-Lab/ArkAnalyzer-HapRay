export enum ComponentCategory {
    ABC_APP = 0,
    ABC_SO = 1,
    ABC_LIB = 2,
    OS_Runtime = 3,
    SYS_SDK = 4,
    RN = 5,
    Flutter = 6,
    WEB = 7,
    SYS_Other = 8,
    UNKNOWN = -1,
}

export interface ComponentCategoryType {
    name: string;
    id: number;
}

export enum OriginKind {
    UNKNOWN = 0,
    FIRST_PARTY = 1,
    OPEN_SOURCE = 2,
    THIRD_PARTY = 3,
}

export interface SoOriginal {
    original: string;
    specific_origin: string;
    broad_category: string;
    sdk_category: string;
    confidence: number;
}

export interface Component {
    id?: number;
    name: string;
    version?: string;
    files?: Set<string>;
    kind: ComponentCategory;
    tag?: string;
}

export function getComponentCategories(): ComponentCategoryType[] {
    return Object.entries(ComponentCategory)
        .filter((e) => !isNaN(e[0] as any))
        .map((e) => ({ name: e[1] as string, id: parseInt(e[0]) }));
}
