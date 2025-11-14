declare module 'd3-hierarchy' {
  export interface HierarchyRectangularNode<Datum> {
    data: Datum;
    value?: number;
    depth: number;
    height: number;
    parent?: HierarchyRectangularNode<Datum>;
    children?: HierarchyRectangularNode<Datum>[];
    x0: number;
    x1: number;
    y0: number;
    y1: number;
    ancestors(): HierarchyRectangularNode<Datum>[];
  }
}

