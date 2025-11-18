// =============================================================================
// File: src/wse/protocols/compression.ts (FIXED V2)
// Description: Enhanced compression utilities with better error handling
// =============================================================================

import pako from 'pako';
import { encode, decode } from '@msgpack/msgpack';
import { logger } from '@/wse';

type CompressionLevel = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | -1;

export class CompressionManager {
  private compressionThreshold: number;
  private compressionLevel: CompressionLevel;

  constructor(
    compressionThreshold = 1024, // bytes - matching backend
    compressionLevel: CompressionLevel = 6 // 1-9, matching backend
  ) {
    this.compressionThreshold = compressionThreshold;
    this.compressionLevel = compressionLevel;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Compression - matching backend implementation
  // ─────────────────────────────────────────────────────────────────────────

  shouldCompress(data: ArrayBuffer | string): boolean {
    const size = typeof data === 'string'
      ? new Blob([data]).size
      : data.byteLength;

    return size > this.compressionThreshold;
  }

  compress(data: ArrayBuffer): ArrayBuffer {
    try {
      // Use pako.deflate to match backend zlib compression
      const compressed = pako.deflate(new Uint8Array(data), { level: this.compressionLevel });
      logger.debug(`Compressed ${data.byteLength} -> ${compressed.byteLength} bytes`);
      return compressed.buffer;
    } catch (error) {
      logger.error('Compression failed:', error);
      throw error;
    }
  }

  decompress(data: ArrayBuffer): ArrayBuffer {
    try {
      const view = new Uint8Array(data);

      // Log the first few bytes for debugging
      logger.debug('Decompressing data:', {
        length: data.byteLength,
        first10Bytes: Array.from(view.slice(0, 10)),
        hexFirst10: Array.from(view.slice(0, 10)).map(b => b.toString(16).padStart(2, '0')).join(' ')
      });

      // Check for zlib header
      if (view.length > 2 && view[0] === 0x78) {
        const compressionMethod = view[1];
        logger.debug(`Detected zlib compression method: 0x${compressionMethod.toString(16)}`);
      }

      // Try standard inflate (for zlib format)
      try {
        const decompressed = pako.inflate(view);
        logger.debug(`Decompressed ${data.byteLength} -> ${decompressed.byteLength} bytes (standard inflate)`);
        return decompressed.buffer;
      } catch (inflateError: any) {
        // Log the specific error
        logger.debug('Standard inflate failed:', inflateError.message);

        // If it's a header check error, it might be rawly deflated
        if (inflateError.message && inflateError.message.includes('header')) {
          logger.debug('Trying raw inflate (no zlib header)...');
          try {
            const decompressed = pako.inflateRaw(view);
            logger.debug(`Decompressed ${data.byteLength} -> ${decompressed.byteLength} bytes (raw inflate)`);
            return decompressed.buffer;
          } catch (rawError) {
            logger.debug('Raw inflate also failed:', rawError);
          }
        }

        // Try gzip as a last resort
        try {
          const decompressed = pako.ungzip(view);
          logger.debug(`Decompressed ${data.byteLength} -> ${decompressed.byteLength} bytes (gzip)`);
          return decompressed.buffer;
        } catch (gzipError) {
          logger.debug('Gzip decompression also failed');
        }

        // Re-throw the original error
        throw inflateError;
      }
    } catch (error) {
      logger.error('Decompression failed:', error);
      logger.error('Failed data first 20 bytes:', Array.from(new Uint8Array(data).slice(0, 20)));
      logger.error('Failed data as hex:', Array.from(new Uint8Array(data).slice(0, 20)).map(b => `0x${b.toString(16).padStart(2, '0')}`).join(' '));
      throw error;
    }
  }

  decompressGzip(data: ArrayBuffer): ArrayBuffer {
    try {
      return pako.ungzip(new Uint8Array(data)).buffer;
    } catch (error) {
      logger.error('Gzip decompression failed:', error);
      throw error;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // MessagePack - matching backend implementation
  // ─────────────────────────────────────────────────────────────────────────

  packMsgPack(data: any): ArrayBuffer {
    try {
      // Use msgpack to match backend
      const encoded = encode(data);
      return encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength) as ArrayBuffer;
    } catch (error) {
      logger.error('MessagePack encoding failed:', error);
      throw error;
    }
  }

  unpackMsgPack(data: ArrayBuffer): any {
    try {
      // Use msgpack to match backend
      return decode(data);
    } catch (error) {
      logger.error('MessagePack decoding failed:', error);
      throw error;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Combined Operations for WebSocket messages
  // ─────────────────────────────────────────────────────────────────────────

  prepareForSending(message: any, useCompression: boolean = true): ArrayBuffer {
    // First, pack with MessagePack
    const packed = this.packMsgPack(message);

    // Then compress if beneficial and enabled
    if (useCompression && this.shouldCompress(packed)) {
      const compressed = this.compress(packed);

      // Only use compression if it actually reduces size
      if (compressed.byteLength < packed.byteLength) {
        // Add compression header 'C':
        const header = new Uint8Array([67, 58]); // 'C:'
        const result = new Uint8Array(header.length + compressed.byteLength);
        result.set(header);
        result.set(new Uint8Array(compressed), header.length);
        return result.buffer;
      }
    }

    // Return uncompressed with MessagePack header 'M':
    const header = new Uint8Array([77, 58]); // 'M:'
    const result = new Uint8Array(header.length + packed.byteLength);
    result.set(header);
    result.set(new Uint8Array(packed), header.length);
    return result.buffer;
  }

  processIncoming(data: ArrayBuffer): any {
    const view = new Uint8Array(data);

    // Check for compression header 'C':
    if (view.length >= 2 && view[0] === 67 && view[1] === 58) {
      const compressed = data.slice(2);
      const decompressed = this.decompress(compressed);
      return this.unpackMsgPack(decompressed);
    }

    // Check for MessagePack header 'M':
    if (view.length >= 2 && view[0] === 77 && view[1] === 58) {
      const packed = data.slice(2);
      return this.unpackMsgPack(packed);
    }

    // Try as a raw MessagePack (backward compatibility)
    try {
      return this.unpackMsgPack(data);
    } catch {
      // If all else fails, try as JSON
      try {
        return JSON.parse(new TextDecoder().decode(data));
      } catch (error) {
        logger.error('Failed to process incoming data:', error);
        throw new Error('Unknown message format');
      }
    }
  }
}

// Singleton instance
export const compressionManager = new CompressionManager();