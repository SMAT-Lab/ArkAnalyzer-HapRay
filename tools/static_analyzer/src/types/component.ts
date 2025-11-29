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
    APP = 1,
    ArkUI = 2,
    OS_Runtime = 3,
    SYS_SDK = 4,
    RN = 5,
    Flutter = 6,
    WEB = 7,
    KMP = 8,
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
    kind: ClassifyCategory;
    tag?: string;
    main?: boolean; // Master component
}

export function getComponentCategories(): Array<ComponentCategoryType> {
    return Object.entries(ComponentCategory)
        .filter(([key]) => !isNaN(Number(key)))
        .map(([key, value]) => ({ name: value as string, id: parseInt(key) }));
}


/**
 * 分类类别接口，支持 1/2/3 级分类
 * 
 * 1 级分类：category (组件大类)
 * 2 级分类：subCategory (小类)
 * 3 级分类：thirdCategory (三级分类)
 */
export interface ClassifyCategory {
    // 1 级分类
    category: ComponentCategory; // 组件大类 ID
    categoryName: string; // 组件大类名称
    
    // 2 级分类（可选）
    subCategory?: number; // 小类 ID
    subCategoryName?: string; // 小类名称
    
    // 3 级分类（可选）
    thirdCategory?: number; // 三级分类 ID
    thirdCategoryName?: string; // 三级分类名称
}


/**
 * 创建 1 级分类
 */
export function createLevel1Category(category: number, categoryName: string): ClassifyCategory {
    return {
        category,
        categoryName,
    };
}

/**
 * 创建 2 级分类
 */
export function createLevel2Category(
    category: number,
    categoryName: string,
    subCategory: number,
    subCategoryName: string
): ClassifyCategory {
    return {
        category,
        categoryName,
        subCategory,
        subCategoryName,
    };
}

/**
 * 创建 3 级分类
 */
export function createLevel3Category(
    category: number,
    categoryName: string,
    subCategory: number,
    subCategoryName: string,
    thirdCategory: number,
    thirdCategoryName: string
): ClassifyCategory {
    return {
        category,
        categoryName,
        subCategory,
        subCategoryName,
        thirdCategory,
        thirdCategoryName,
    };
}

/**
 * 获取分类层级数
 */
export function getCategoryLevel(category: ClassifyCategory): number {
    if (category.thirdCategory !== undefined && category.thirdCategoryName) {
        return 3;
    }
    if (category.subCategory !== undefined && category.subCategoryName) {
        return 2;
    }
    return 1;
}

/**
 * 获取分类的完整路径（用于显示）
 */
export function getCategoryPath(category: ClassifyCategory, separator = ' > '): string {
    const parts: Array<string> = [category.categoryName];
    
    if (category.subCategoryName) {
        parts.push(category.subCategoryName);
    }
    
    if (category.thirdCategoryName) {
        parts.push(category.thirdCategoryName);
    }
    
    return parts.join(separator);
}