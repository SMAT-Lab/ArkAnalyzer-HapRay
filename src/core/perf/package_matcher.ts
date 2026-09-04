import type { KotlinModule } from '../../config/types';

// Trie 节点接口
interface TrieNode {
    children: Map<string, TrieNode>;
    moduleName: string | null;
    isEnd: boolean;
}

// 前缀树快速匹配
export class PackageMatcher {
    private root: TrieNode;
    private modules: Array<KotlinModule>;

    constructor(modules: Array<KotlinModule>) {
        this.modules = modules;
        this.root = this.buildTrie();
    }

    /**
     * 构建 Trie 数据结构
     */
    private buildTrie(): TrieNode {
        const root: TrieNode = {
            children: new Map(),
            moduleName: null,
            isEnd: false,
        };

        // 添加库的命名空间
        for (const config of this.modules) {
            this.addToTrie(root, config.namespace, config.name);
        }

        return root;
    }

    /**
     * 将命名空间添加到 Trie 中
     */
    private addToTrie(root: TrieNode, namespace: string, moduleName: string): void {
        const parts = namespace.split('.');
        let node = root;

        for (const part of parts) {
            if (!node.children.has(part)) {
                node.children.set(part, {
                    children: new Map(),
                    moduleName: null,
                    isEnd: false,
                });
            }
            node = node.children.get(part)!;
        }

        node.isEnd = true;
        node.moduleName = moduleName;
    }

    /**
     * 查找最具体的模块匹配（最长的命名空间匹配）
     * 使用 Trie 数据结构实现高效匹配
     */
    findMostSpecificModule(packageName: string): string | null {
        const parts = packageName.split('.');
        let node = this.root;
        let lastMatch: string | null = null;

        for (const part of parts) {
            if (!node.children.has(part)) {
                break;
            }

            node = node.children.get(part)!;

            if (node.isEnd && node.moduleName) {
                lastMatch = node.moduleName;
            }
        }

        return lastMatch;
    }
}
