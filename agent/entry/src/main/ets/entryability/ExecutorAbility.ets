import { AbilityConstant, UIAbility, Want } from "@kit.AbilityKit";
import { window } from "@kit.ArkUI";
import { hilog } from '@kit.PerformanceAnalysisKit';
import { TestRunner } from "../common/TestRunner";


const DOMAIN = 0x0000;
const TAG = 'ExecutorAbility';

interface TestWantParams {
  testSuite: string;
  testCase: string;
}

export default class ExecutorAbility extends UIAbility {
  private want: Want | null = null;

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    this.want = want;
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    // Main window is created, set main page for this ability
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onWindowStageCreate');

    const params: TestWantParams =
      {
        testSuite: this.want?.parameters?.testSuite,
        testCase: this.want?.parameters?.testCase
      } as TestWantParams;

    TestRunner.getInstance()?.getTestCase(params.testSuite, params.testCase).then((testCase) => {
      let page = testCase?.getTargetPage() || 'pages/Index';
      windowStage.loadContent(page, (err) => {
        if (err.code) {
          hilog.error(DOMAIN, TAG, 'Failed to load the content. Cause: %{public}s', JSON.stringify(err));
          return;
        }
        hilog.info(DOMAIN, TAG, 'Succeeded in loading the content.');
      });
    })
  }
}