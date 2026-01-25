import bundleManager from '@ohos.bundle.bundleManager';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { TestCase } from 'test_suite/src/main/ets/common/TestCase';
import { window } from '@kit.ArkUI';

const DOMAIN = 0x0000;
const TAG = 'TestRunner';

export interface TestSuite {
  name: string;
  module: ESObject;
  testCases: string[];
}

export class TestRunner {
  private static instance: TestRunner;

  private testSuites: Map<string, TestSuite> = new Map();
  private init: boolean = false;

  private constructor() {
  }

  public static getInstance(): TestRunner {
    if (!TestRunner.instance) {
      TestRunner.instance = new TestRunner();
    }
    return TestRunner.instance;
  }

  async getTestCase(testSuite: string, testCase: string): Promise<TestCase | null> {
    await this.initialize();
    if (!this.testSuites.has(testSuite)) {
      return null;
    }

    try {
      const testModule = this.testSuites.get(testSuite)!;
      let instance = new testModule.module[testCase]() as TestCase;
      return instance;
    } catch (err) {
      hilog.error(DOMAIN, TAG, 'Failed to new TestCase. Cause: %{public}s', JSON.stringify(err));
    }
    return null;
  }

  /**
   * 获取所有可用测试模块信息
   */
  async getAvailableTestSuites(): Promise<Array<TestSuite>> {
    await this.initialize();
    return Array.from(this.testSuites.values());
  }

  private async initialize(): Promise<void> {
    if (this.init) {
      return;
    }
    await this.discoverTestSuite();
    this.init = true;
  }

  // 发现并加载所有测试模块
  private async discoverTestSuite(): Promise<void> {
    try {
      // 获取所有已安装应用（包括HSP）
      const bundleInfo = await bundleManager.getBundleInfoForSelf(
        bundleManager.BundleFlag.GET_BUNDLE_INFO_WITH_HAP_MODULE |
        bundleManager.BundleFlag.GET_BUNDLE_INFO_WITH_METADATA
      );

      for (const hapModule of bundleInfo.hapModulesInfo) {
        await this.checkAndLoadModule(hapModule);
      }
    } catch (error) {
      console.error('Failed to discover test modules:', error);
    }
  }

  // 检查并加载测试模块
  private async checkAndLoadModule(
    moduleInfo: bundleManager.HapModuleInfo
  ): Promise<void> {
    // only load HSP
    if (moduleInfo.type !== bundleManager.ModuleType.SHARED) {
      return;
    }

    // 动态导入模块
    const moduleName: string = moduleInfo.name;
    try {
      const module: ESObject = (await import(moduleName)) as ESObject;
      if (module) {
        let testSuite: TestSuite = { name: moduleName, module: module, testCases: [] };
        for (const index of Object.entries<Array<ESObject>>(module).keys()) {
          let arr = Object.entries<object>(module)[index];
          let key = arr[0];
          let value = arr[1];
          if (typeof value.constructor === 'function' && key.endsWith('Test')) {
            testSuite.testCases.push(key)
          }
        }
        this.testSuites.set(moduleName, testSuite);
      }
    } catch (importError) {
      hilog.error(DOMAIN, TAG, `Failed to import test module ${moduleName}:`, importError);
    }
  }
}