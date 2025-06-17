export abstract class TestCase {
  public constructor() {
  }

  public abstract getTargetPage(): string;

  public async run(): Promise<void> {
    this.setup()
    this.process();
    this.teardown();
  }

  protected async setup(): Promise<void> {

  }

  protected async process(): Promise<void> {

  }

  protected async teardown(): Promise<void> {

  }
}