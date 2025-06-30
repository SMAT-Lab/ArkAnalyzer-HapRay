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
import { ItemData } from "./ItemData";

export const TAB_TITLES: string[] = ['News', 'Hot', 'Video', 'Tech', 'Travel'];

const NEWS_TITLES: string[] =
  ['Embark on the journey of integrating intelligence and innovation, join hands to build a new generation of demonstration cities, collaborate on creation, provide new solutions, and create a new era',
    'In the era of data awakening, redefining data storage',
    'High end all flash memory won the top recommendation on annual storage data list, ranking first in the recommendation list',
    'Deeply integrating new technologies with the aviation industry, based on cloud, data, and intelligence as the core of the digital base, jointly cooperating to create solutions to help aviation efficiency',
    'Innovation leads, with actions and words, to jointly build new high-quality communication and new development',
    'To jointly build new high-quality communication and new development'];

const NEWS_FROMS: string[] = ['Comment', 'News', 'Discuss'];

export function genMockItemData(size: number): ItemData[] {
  const res: ItemData[] = [];
  for (let i = 0; i < size; i++) {
    const data = new ItemData('' + i, i % 3);
    data.title = NEWS_TITLES[i % NEWS_TITLES.length];
    data.from = NEWS_FROMS[i % NEWS_FROMS.length];
    data.tail = '15 minutes ago';
    data.duration = '03:12';
    res.push(data);
  }
  return res;
}
