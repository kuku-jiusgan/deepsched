import { nextTick, unref, type Ref } from 'vue'
import dayjs from 'dayjs'

type MaybeRef<T> = T | Ref<T>

export async function centerGanttTimelineOnCurrentTime(
  viewportRef: Ref<HTMLElement | null>,
  columnWidth: MaybeRef<number>,
) {
  await nextTick()
  const viewport = viewportRef.value
  if (!viewport) return
  const now = dayjs()
  const hourOffset = now.hour() + now.minute() / 60
  const currentTimeX = hourOffset * unref(columnWidth)
  viewport.scrollLeft = Math.max(0, currentTimeX - viewport.clientWidth / 2)
}

export async function scrollGanttTimelineToStart(viewportRef: Ref<HTMLElement | null>) {
  await nextTick()
  if (viewportRef.value) viewportRef.value.scrollLeft = 0
}
