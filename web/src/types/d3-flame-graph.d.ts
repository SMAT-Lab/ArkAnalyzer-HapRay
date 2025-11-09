declare module 'd3-flame-graph' {
  import type { Selection } from 'd3-selection';
  import type { HierarchyRectangularNode } from 'd3-hierarchy';
  import type { FlamegraphTooltipInstance } from 'd3-flame-graph/dist/d3-flamegraph-tooltip.js';

  export interface FlamegraphDatum {
    name?: string;
    value?: number;
    children?: FlamegraphDatum[];
    tooltip?: string;
    [key: string]: unknown;
  }

  export type FlamegraphTooltip = FlamegraphTooltipInstance<
    HierarchyRectangularNode<FlamegraphDatum>
  >;

  export interface FlameGraph {
    (selection: Selection<Element, FlamegraphDatum, Element, unknown>): void;
    height(value: number): FlameGraph;
    width(value: number): FlameGraph;
    cellHeight(value: number): FlameGraph;
    transitionDuration(value: number): FlameGraph;
    minFrameSize(value: number): FlameGraph;
    tooltip(tooltip: FlamegraphTooltip | null): FlameGraph;
    label(
      formatter: (node: HierarchyRectangularNode<FlamegraphDatum>) => string,
    ): FlameGraph;
    sort(
      comparator: (
        a: HierarchyRectangularNode<FlamegraphDatum>,
        b: HierarchyRectangularNode<FlamegraphDatum>,
      ) => number,
    ): FlameGraph;
  }

  export function flamegraph(): FlameGraph;

  export function flamegraphTooltip(): FlamegraphTooltip;
}
