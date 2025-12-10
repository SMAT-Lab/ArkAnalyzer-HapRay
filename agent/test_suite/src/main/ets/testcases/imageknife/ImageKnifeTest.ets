import { TestCase } from "../../common/TestCase";

export class ImageKnifeDownSamplingPageTest extends TestCase {
  public getTargetPage(): string {
    return '@bundle:arkanalyzer.hapray.agent/test_suite/ets/testcases/imageknife/pages/DownSamplingPage';
  }
}

export class ImageKnifeDefaultPageTest extends TestCase {
  public getTargetPage(): string {
    return '@bundle:arkanalyzer.hapray.agent/test_suite/ets/testcases/imageknife/pages/DefaultPage';
  }
}