export async function computeWaveformPeaks(src: string, targetPoints: number): Promise<number[]> {
  const response = await fetch(src)
  const arrayBuffer = await response.arrayBuffer()
  const AudioContextCtor = window.AudioContext
  const audioContext = new AudioContextCtor()
  try {
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)
    const channelData = audioBuffer.getChannelData(0)
    const blockSize = Math.max(1, Math.floor(channelData.length / targetPoints))
    const peaks: number[] = []
    for (let i = 0; i < targetPoints; i += 1) {
      const start = i * blockSize
      let max = 0
      for (let j = start; j < start + blockSize && j < channelData.length; j += 1) {
        const abs = Math.abs(channelData[j])
        if (abs > max) max = abs
      }
      peaks.push(max)
    }
    return peaks
  } finally {
    await audioContext.close()
  }
}
