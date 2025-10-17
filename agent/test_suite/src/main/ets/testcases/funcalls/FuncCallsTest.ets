import { TestCase } from "../../common/TestCase";

export class FuncCallsTest extends TestCase {
  public getTargetPage(): string {
    return '@bundle:arkanalyzer.hapray.agent/test_suite/ets/testcases/funcalls/pages/CallNativePage';
  }
}