import { TestCase } from "../../common/TestCase";

export class ImageKnifeDownSamplingTest extends TestCase {
  public getTargetPage(): string {
    return '@bundle:arkanalyzer.hapray.agent/test_suite/ets/testcases/imageknife/pages/DownSamplingPage';
  }
}

export class ImageKnifeDefaultTest extends TestCase {
  public getTargetPage(): string {
    return '@bundle:arkanalyzer.hapray.agent/test_suite/ets/testcases/imageknife/pages/DefaultPage';
  }
}