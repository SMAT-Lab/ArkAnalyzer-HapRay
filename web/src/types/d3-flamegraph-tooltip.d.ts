declare module 'd3-flame-graph/dist/d3-flamegraph-tooltip.js' {
  import type { HierarchyRectangularNode } from 'd3-hierarchy';
  import type { FlamegraphDatum } from 'd3-flame-graph';

  export interface FlamegraphTooltipInstance<Datum = HierarchyRectangularNode<FlamegraphDatum>> {
    (selection: unknown): void;
    show(data: Datum): void;
    hide(): void;
    html(
      value?:
        | string
        | ((data: Datum) => string)
    ): FlamegraphTooltipInstance<Datum>;
  }

  export function defaultFlamegraphTooltip<
    Datum = HierarchyRectangularNode<FlamegraphDatum>,
  >(): FlamegraphTooltipInstance<Datum>;
}

