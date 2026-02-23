import { ref } from "vue"

const MIN_WIDTH = 160
const MAX_WIDTH = 400
const DEFAULT_WIDTH = 220

export function useSidebarResize() {
  const sidebarWidth = ref(DEFAULT_WIDTH)

  const onResizeStart = (e: MouseEvent): void => {
    if (e.buttons !== 1) return
    e.preventDefault()

    const onMove = (move: MouseEvent) => {
      const next = sidebarWidth.value + move.movementX
      sidebarWidth.value = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, next))
    }

    const onUp = () => {
      document.removeEventListener("mousemove", onMove)
      document.removeEventListener("mouseup", onUp)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }

    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    document.addEventListener("mousemove", onMove)
    document.addEventListener("mouseup", onUp)
  }

  return {
    sidebarWidth,
    onResizeStart,
  }
}
