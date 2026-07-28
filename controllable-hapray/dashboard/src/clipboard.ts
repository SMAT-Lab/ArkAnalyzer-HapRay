export interface ClipboardWriter {
  writeText(value: string): Promise<void>
}

export async function copyText(
  value: string,
  clipboard: ClipboardWriter = navigator.clipboard,
  fallback: (text: string) => boolean = legacyCopy,
): Promise<void> {
  try {
    await clipboard.writeText(value)
  } catch (error) {
    if (!fallback(value)) throw error
  }
}

function legacyCopy(value: string): boolean {
  const input = document.createElement('textarea')
  input.value = value
  input.setAttribute('readonly', '')
  input.style.position = 'fixed'
  input.style.opacity = '0'
  document.body.append(input)
  input.select()
  const copied = document.execCommand('copy')
  input.remove()
  return copied
}
