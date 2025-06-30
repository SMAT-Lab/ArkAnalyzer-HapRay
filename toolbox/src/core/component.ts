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

export enum ComponentCategory {
    APP_ABC = 0,
    APP_SO = 1,
    APP_LIB = 2,
    OS_Runtime = 3,
    SYS_SDK = 4,
    RN = 5,
    Flutter = 6,
    WEB = 7,
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

export interface Component {
    id?: number;
    name: string;
    version?: string;
    files?: Set<string>;
    kind: ComponentCategory;
    tag?: string;
    main?: boolean; // Master component
}

export function getComponentCategories(): Array<ComponentCategoryType> {
    return Object.entries(ComponentCategory)
        .filter(([key]) => !isNaN(Number(key)))
        .map(([key, value]) => ({ name: value as string, id: parseInt(key) }));
}
