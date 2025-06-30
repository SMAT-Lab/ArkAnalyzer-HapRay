import { TestCase } from "../../common/TestCase";

export class ComponentReusableTest extends TestCase {
  public getTargetPage(): string {
    return '@bundle:arkanalyzer.hapray.agent/test_suite/ets/testcases/reusable/pages/ReusablePage';
  }
}

export class ComponentNoReusableTest extends TestCase {
  public getTargetPage(): string {
    return '@bundle:arkanalyzer.hapray.agent/test_suite/ets/testcases/reusable/pages/NoReusablePage';
  }
}