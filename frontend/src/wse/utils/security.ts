// =============================================================================
// File: src/wse/utils/security.ts
// Description: Enhanced Security utilities for WebSocket Event System (FIXED)
// =============================================================================

import { logger } from '@/wse';

// Check for Web Crypto API availability
if (typeof window !== 'undefined' && !window.crypto?.subtle) {
  logger.warn('Web Crypto API not available. HTTPS required for crypto.subtle');
}

// Security error types
export class SecurityError extends Error {
  constructor(
    message: string,
    public readonly code: 'ENCRYPTION_FAILED' | 'DECRYPTION_FAILED' |
           'SIGNING_FAILED' | 'VERIFICATION_FAILED' | 'KEY_GENERATION_FAILED' |
           'KEY_EXCHANGE_FAILED' | 'REPLAY_ATTACK' | 'NEGOTIATION_FAILED',
    public readonly details?: any
  ) {
    super(message);
    this.name = 'SecurityError';
  }
}

// Nonce cache for replay attack prevention with size limits
class NonceCache {
  private readonly cache = new Map<string, number>();
  private readonly cleanupInterval: NodeJS.Timeout;
  private readonly maxSize = 10000; // Prevent unbounded growth

  constructor(private readonly maxAge: number = 300000) { // 5 minutes default
    // Cleanup old nonces every minute
    this.cleanupInterval = setInterval(() => this.cleanup(), 60000);
  }

  add(nonce: string): void {
    this.cache.set(nonce, Date.now());

    // Immediate size check
    if (this.cache.size > this.maxSize * 1.2) {
      this.cleanup();
    }
  }

  has(nonce: string): boolean {
    return this.cache.has(nonce);
  }

  private cleanup(): void {
    const now = Date.now();

    // Clean by age
    for (const [nonce, timestamp] of this.cache.entries()) {
      if (now - timestamp > this.maxAge) {
        this.cache.delete(nonce);
      }
    }

    // Clean by size if still too large
    if (this.cache.size > this.maxSize) {
      const sortedEntries = Array.from(this.cache.entries())
        .sort((a, b) => a[1] - b[1]);
      const toRemove = sortedEntries.slice(0, this.cache.size - this.maxSize);
      toRemove.forEach(([nonce]) => this.cache.delete(nonce));
    }
  }

  destroy(): void {
    clearInterval(this.cleanupInterval);
    this.cache.clear();
  }
}

export class SecurityManager {
  private encryptionEnabled = false;
  private messageSigningEnabled = false;
  private encryptionKey: CryptoKey | null = null;
  private signingKey: CryptoKey | null = null;
  private keyRotationInterval: number | null = null;
  private lastKeyRotation: number | null = null;
  private keyRotationTimer: NodeJS.Timeout | null = null;
  private keyRotationFailures = 0;

  // Enhanced security features
  private readonly nonceCache = new NonceCache();
  private sessionKeyPair: CryptoKeyPair | null = null;
  private sharedSecret: CryptoKey | null = null;
  private serverPublicKey: CryptoKey | null = null;

  // IV tracking for encryption
  private usedIVs = new Set<string>();

  // Backend compatibility
  private backendCompatibilityMode = false;
  private readonly supportedAlgorithms = {
    encryption: 'AES-GCM',
    signing: 'HMAC-SHA256',
    keyExchange: 'ECDH-P256'
  };

  async initialize(config: {
    encryptionEnabled: boolean;
    messageSigningEnabled: boolean;
    keyRotationInterval?: number;
    backendCompatibilityMode?: boolean;
  }) {
    try {
      this.encryptionEnabled = config.encryptionEnabled;
      this.messageSigningEnabled = config.messageSigningEnabled;
      this.keyRotationInterval = config.keyRotationInterval || 3600000; // 1-hour default
      this.backendCompatibilityMode = config.backendCompatibilityMode || false;

      if (this.encryptionEnabled) {
        await this.generateEncryptionKey();
        logger.info('Encryption enabled for WebSocket messages with AES-GCM');
      }

      if (this.messageSigningEnabled) {
        await this.generateSigningKey();
        logger.info('Message signing enabled for WebSocket messages with HMAC-SHA256');
      }

      // Generate a key pair for key exchange
      await this.generateKeyPair();

      // Setup key rotation if enabled
      if (this.encryptionEnabled || this.messageSigningEnabled) {
        this.scheduleKeyRotation();
      }
    } catch (error) {
      throw new SecurityError(
        'Failed to initialize security manager',
        'KEY_GENERATION_FAILED',
        error
      );
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Key Generation
  // ─────────────────────────────────────────────────────────────────────────

  private async generateEncryptionKey(): Promise<void> {
    try {
      this.encryptionKey = await crypto.subtle.generateKey(
        {
          name: 'AES-GCM',
          length: 256
        },
        true, // extractable
        ['encrypt', 'decrypt']
      );
      logger.debug('Generated new AES-GCM encryption key');
    } catch (error) {
      throw new SecurityError(
        'Failed to generate encryption key',
        'KEY_GENERATION_FAILED',
        error
      );
    }
  }

  private async generateSigningKey(): Promise<void> {
    try {
      this.signingKey = await crypto.subtle.generateKey(
        {
          name: 'HMAC',
          hash: 'SHA-256'
        },
        true, // extractable
        ['sign', 'verify']
      );
      logger.debug('Generated new HMAC signing key');
    } catch (error) {
      throw new SecurityError(
        'Failed to generate signing key',
        'KEY_GENERATION_FAILED',
        error
      );
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Key Exchange (ECDH)
  // ─────────────────────────────────────────────────────────────────────────

  private async generateKeyPair(): Promise<void> {
    try {
      this.sessionKeyPair = await crypto.subtle.generateKey(
        {
          name: 'ECDH',
          namedCurve: 'P-256'
        },
        true,
        ['deriveKey', 'deriveBits']
      );
      logger.debug('Generated ECDH key pair for key exchange');
    } catch (error) {
      throw new SecurityError(
        'Failed to generate key pair',
        'KEY_GENERATION_FAILED',
        error
      );
    }
  }

  async getPublicKey(): Promise<JsonWebKey | null> {
    if (!this.sessionKeyPair) return null;

    try {
      return await crypto.subtle.exportKey('jwk', this.sessionKeyPair.publicKey);
    } catch (error) {
      logger.error('Failed to export public key:', error);
      return null;
    }
  }

  async setServerPublicKey(publicKeyJwk: JsonWebKey): Promise<void> {
    try {
      // Validate the key first
      if (!publicKeyJwk.kty || publicKeyJwk.kty !== 'EC') {
        throw new Error('Invalid key type for ECDH');
      }

      if (!publicKeyJwk.crv || publicKeyJwk.crv !== 'P-256') {
        throw new Error('Invalid curve for ECDH');
      }

      this.serverPublicKey = await crypto.subtle.importKey(
        'jwk',
        publicKeyJwk,
        {
          name: 'ECDH',
          namedCurve: 'P-256'
        },
        false,
        []
      );

      // Derive shared secret if we have both keys
      if (this.sessionKeyPair && this.serverPublicKey) {
        await this.deriveSharedSecret();
      }
    } catch (error) {
      // Reset on failure
      this.serverPublicKey = null;
      throw new SecurityError(
        'Failed to import server public key',
        'KEY_EXCHANGE_FAILED',
        error
      );
    }
  }

  private async deriveSharedSecret(): Promise<void> {
    if (!this.sessionKeyPair || !this.serverPublicKey) return;

    try {
      // Derive shared secret bits
      const sharedSecretBits = await crypto.subtle.deriveBits(
        {
          name: 'ECDH',
          public: this.serverPublicKey
        },
        this.sessionKeyPair.privateKey,
        256
      );

      // Use shared secret to derive an encryption key
      this.sharedSecret = await crypto.subtle.importKey(
        'raw',
        sharedSecretBits,
        'HKDF',
        false,
        ['deriveKey']
      );

      // Derive an actual encryption key from a shared secret
      this.encryptionKey = await crypto.subtle.deriveKey(
        {
          name: 'HKDF',
          hash: 'SHA-256',
          salt: new TextEncoder().encode('wse-encryption'),
          info: new TextEncoder().encode('aes-gcm-key')
        },
        this.sharedSecret,
        { name: 'AES-GCM', length: 256 },
        true,
        ['encrypt', 'decrypt']
      );

      logger.info('Derived shared encryption key from ECDH exchange');
    } catch (error) {
      throw new SecurityError(
        'Failed to derive shared secret',
        'KEY_EXCHANGE_FAILED',
        error
      );
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Enhanced Encryption/Decryption with Backend Compatibility
  // ─────────────────────────────────────────────────────────────────────────

  async encryptMessage(data: string): Promise<ArrayBuffer | null> {
    if (!this.encryptionEnabled || !this.encryptionKey) return null;

    try {
      const encoder = new TextEncoder();
      const encoded = encoder.encode(data);

      // Generate unique IV
      let iv: Uint8Array;
      let ivHex: string;
      let attempts = 0;

      do {
        iv = crypto.getRandomValues(new Uint8Array(12)); // 96-bit IV for GCM
        ivHex = Array.from(iv).map(b => b.toString(16).padStart(2, '0')).join('');
        attempts++;

        if (attempts > 10) {
          // Clear IV cache if we're having trouble finding a unique IV
          this.usedIVs.clear();
        }
      } while (this.usedIVs.has(ivHex) && attempts < 100);

      this.usedIVs.add(ivHex);

      // Clean old IVs periodically (they can be reused after key rotation)
      if (this.usedIVs.size > 10000) {
        this.usedIVs.clear();
      }

      // Encrypt the data
      const encrypted = await crypto.subtle.encrypt(
        {
          name: 'AES-GCM',
          iv: iv as BufferSource
        },
        this.encryptionKey,
        encoded
      );

      // Combine IV and encrypted data
      // Format: [IV (12 bytes)][Encrypted Data]
      const combined = new Uint8Array(iv.length + encrypted.byteLength);
      combined.set(iv, 0);
      combined.set(new Uint8Array(encrypted), iv.length);

      return combined.buffer;
    } catch (error) {
      throw new SecurityError(
        'Encryption failed',
        'ENCRYPTION_FAILED',
        error
      );
    }
  }

  async decryptMessage(data: ArrayBuffer): Promise<string | null> {
    if (!this.encryptionEnabled || !this.encryptionKey) return null;

    try {
      const dataArray = new Uint8Array(data);

      // Extract IV and encrypted data
      const iv = dataArray.slice(0, 12);
      const encrypted = dataArray.slice(12);

      // Decrypt
      const decrypted = await crypto.subtle.decrypt(
        {
          name: 'AES-GCM',
          iv: iv
        },
        this.encryptionKey,
        encrypted
      );

      const decoder = new TextDecoder();
      return decoder.decode(decrypted);
    } catch (error) {
      throw new SecurityError(
        'Decryption failed',
        'DECRYPTION_FAILED',
        error
      );
    }
  }

  // Backend-compatible encryption with 'E:' prefix
  async encryptForTransport(data: string): Promise<ArrayBuffer> {
    const encrypted = await this.encryptMessage(data);
    if (!encrypted) {
      const encoded = new TextEncoder().encode(data);
      return encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength) as ArrayBuffer;
    }

    // Add 'E:' prefix for backend compatibility
    const prefix = new TextEncoder().encode('E:');
    const combined = new Uint8Array(prefix.length + encrypted.byteLength);
    combined.set(prefix, 0);
    combined.set(new Uint8Array(encrypted), prefix.length);

    return combined.buffer;
  }

  async decryptFromTransport(data: ArrayBuffer): Promise<string | null> {
    const view = new Uint8Array(data);

    // Check for the 'E:' prefix
    if (view.length >= 2 && view[0] === 69 && view[1] === 58) { // 'E:'
      return this.decryptMessage(data.slice(2));
    }

    // Try direct decryption
    return this.decryptMessage(data);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Enhanced Message Signing with Replay Attack Prevention
  // ─────────────────────────────────────────────────────────────────────────

  async signMessageWithTimestamp(data: any): Promise<{
    signature: string;
    timestamp: number;
    nonce: string;
  } | null> {
    if (!this.messageSigningEnabled || !this.signingKey) return null;

    try {
      const timestamp = Date.now();
      const nonce = await this.generateNonce();

      // Store nonce to prevent replay
      this.nonceCache.add(nonce);

      const messageToSign = {
        data,
        timestamp,
        nonce
      };

      const encoder = new TextEncoder();
      const encoded = encoder.encode(JSON.stringify(messageToSign));

      const signature = await crypto.subtle.sign(
        'HMAC',
        this.signingKey,
        encoded
      );

      return {
        signature: this.arrayBufferToBase64(signature),
        timestamp,
        nonce
      };
    } catch (error) {
      throw new SecurityError(
        'Message signing failed',
        'SIGNING_FAILED',
        error
      );
    }
  }

  async verifySignatureWithTimestamp(
    data: any,
    signature: string,
    timestamp: number,
    nonce: string,
    maxAgeMs: number = 300000 // 5 minutes
  ): Promise<boolean> {
    if (!this.messageSigningEnabled || !this.signingKey) return true;

    try {
      // Check timestamp freshness
      if (Date.now() - timestamp > maxAgeMs) {
        logger.error('Message timestamp too old, possible replay attack');
        return false;
      }

      // Check nonce hasn't been used
      if (this.nonceCache.has(nonce)) {
        logger.error('Nonce already used, possible replay attack');
        return false;
      }

      // Add nonce to cache
      this.nonceCache.add(nonce);

      const messageToVerify = { data, timestamp, nonce };
      const encoder = new TextEncoder();
      const encoded = encoder.encode(JSON.stringify(messageToVerify));

      const signatureBuffer = this.base64ToArrayBuffer(signature);

      return await crypto.subtle.verify(
        'HMAC',
        this.signingKey,
        signatureBuffer,
        encoded
      );
    } catch (error) {
      logger.error('Signature verification failed:', error);
      return false;
    }
  }

  // Legacy signing methods for compatibility
  async signMessage(data: any): Promise<string | null> {
    if (!this.messageSigningEnabled || !this.signingKey) return null;

    try {
      const encoder = new TextEncoder();
      const encoded = encoder.encode(JSON.stringify(data));

      const signature = await crypto.subtle.sign(
        'HMAC',
        this.signingKey,
        encoded
      );

      return this.arrayBufferToBase64(signature);
    } catch (error) {
      logger.error('Message signing failed:', error);
      return null;
    }
  }

  async verifySignature(data: any, signature: string): Promise<boolean> {
    if (!this.messageSigningEnabled || !this.signingKey) return true;

    try {
      const encoder = new TextEncoder();
      const encoded = encoder.encode(JSON.stringify(data));

      const signatureBuffer = this.base64ToArrayBuffer(signature);

      return await crypto.subtle.verify(
        'HMAC',
        this.signingKey,
        signatureBuffer,
        encoded
      );
    } catch (error) {
      logger.error('Signature verification failed:', error);
      return false;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Security Negotiation
  // ─────────────────────────────────────────────────────────────────────────

  async negotiateSecurity(serverCapabilities: {
    encryption?: boolean;
    signing?: boolean;
    algorithms?: string[];
    publicKey?: JsonWebKey;
  }): Promise<{
    encryption: boolean;
    signing: boolean;
    keyExchange: boolean;
    algorithms: {
      encryption: string;
      signing: string;
      keyExchange: string;
    };
  }> {
    try {
      // Validate algorithms if provided
      if (serverCapabilities.algorithms) {
        const supportedAlgoList = Object.values(this.supportedAlgorithms);
        const unsupported = serverCapabilities.algorithms.filter(
          algo => !supportedAlgoList.includes(algo)
        );
        if (unsupported.length > 0) {
          logger.warn(`Server requested unsupported algorithms: ${unsupported.join(', ')}`);
        }
      }

      // Only enable features that both client and server support
      this.encryptionEnabled = this.encryptionEnabled && (serverCapabilities.encryption ?? false);
      this.messageSigningEnabled = this.messageSigningEnabled && (serverCapabilities.signing ?? false);

      // Exchange keys if server provides public key
      if (serverCapabilities.publicKey && this.encryptionEnabled) {
        await this.setServerPublicKey(serverCapabilities.publicKey);
      }

      const negotiated = {
        encryption: this.encryptionEnabled,
        signing: this.messageSigningEnabled,
        keyExchange: !!serverCapabilities.publicKey,
        algorithms: this.supportedAlgorithms
      };

      logger.info('Security negotiated:', negotiated);
      return negotiated;
    } catch (error) {
      throw new SecurityError(
        'Security negotiation failed',
        'NEGOTIATION_FAILED',
        error
      );
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Key Management
  // ─────────────────────────────────────────────────────────────────────────

  private scheduleKeyRotation(): void {
    if (!this.keyRotationInterval || this.keyRotationTimer) return;

    this.keyRotationTimer = setInterval(async () => {
      try {
        await this.rotateKeys();
        this.keyRotationFailures = 0; // Reset on success
      } catch (error) {
        logger.error('Key rotation failed:', error);
        this.keyRotationFailures++;

        // Stop rotation after 3 consecutive failures
        if (this.keyRotationFailures >= 3) {
          logger.error('Key rotation disabled after 3 consecutive failures');
          if (this.keyRotationTimer) {
            clearInterval(this.keyRotationTimer);
            this.keyRotationTimer = null;
          }
        }
      }
    }, this.keyRotationInterval);
  }

  async rotateKeys(): Promise<void> {
    logger.info('Rotating cryptographic keys');

    try {
      if (this.encryptionEnabled) {
        await this.generateEncryptionKey();
        // Clear IV cache on key rotation
        this.usedIVs.clear();
      }

      if (this.messageSigningEnabled) {
        await this.generateSigningKey();
      }

      // Generate a new key pair for future key exchanges
      await this.generateKeyPair();

      this.lastKeyRotation = Date.now();

      // Notify about key rotation
      logger.info('Keys rotated successfully');
    } catch (error) {
      logger.error('Key rotation failed:', error);
      throw error; // Re-throw for the scheduler to handle
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Key Derivation Function (KDF)
  // ─────────────────────────────────────────────────────────────────────────

  async deriveKey(
    password: string,
    salt: Uint8Array,
    iterations: number = 600000 // Updated for 2025 standards while maintaining backward compatibility
  ): Promise<CryptoKey> {
    try {
      const encoder = new TextEncoder();
      const keyMaterial = await crypto.subtle.importKey(
        'raw',
        encoder.encode(password),
        'PBKDF2',
        false,
        ['deriveBits', 'deriveKey']
      );

      return crypto.subtle.deriveKey(
        {
          name: 'PBKDF2',
          salt: salt as BufferSource,
          iterations: iterations,
          hash: 'SHA-256'
        },
        keyMaterial,
        { name: 'AES-GCM', length: 256 },
        true,
        ['encrypt', 'decrypt']
      );
    } catch (error) {
      throw new SecurityError(
        'Key derivation failed',
        'KEY_GENERATION_FAILED',
        error
      );
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Key Export/Import
  // ─────────────────────────────────────────────────────────────────────────

  async exportKeys(): Promise<{
    encryptionKey?: JsonWebKey;
    signingKey?: JsonWebKey;
    publicKey?: JsonWebKey;
  }> {
    const exported: any = {};

    try {
      if (this.encryptionKey) {
        exported.encryptionKey = await crypto.subtle.exportKey('jwk', this.encryptionKey);
      }

      if (this.signingKey) {
        exported.signingKey = await crypto.subtle.exportKey('jwk', this.signingKey);
      }

      if (this.sessionKeyPair) {
        exported.publicKey = await crypto.subtle.exportKey('jwk', this.sessionKeyPair.publicKey);
      }

      return exported;
    } catch (error) {
      logger.error('Failed to export keys:', error);
      return {};
    }
  }

  async importKeys(keys: {
    encryptionKey?: JsonWebKey;
    signingKey?: JsonWebKey;
  }): Promise<void> {
    try {
      if (keys.encryptionKey) {
        this.encryptionKey = await crypto.subtle.importKey(
          'jwk',
          keys.encryptionKey,
          { name: 'AES-GCM' },
          true,
          ['encrypt', 'decrypt']
        );
      }

      if (keys.signingKey) {
        this.signingKey = await crypto.subtle.importKey(
          'jwk',
          keys.signingKey,
          { name: 'HMAC', hash: 'SHA-256' },
          true,
          ['sign', 'verify']
        );
      }
    } catch (error) {
      throw new SecurityError(
        'Failed to import keys',
        'KEY_GENERATION_FAILED',
        error
      );
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Utilities
  // ─────────────────────────────────────────────────────────────────────────

  async generateNonce(length: number = 16): Promise<string> {
    const nonce = crypto.getRandomValues(new Uint8Array(length));
    return this.arrayBufferToBase64(nonce.buffer)
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');
  }

  async generateSalt(length: number = 16): Promise<Uint8Array> {
    return crypto.getRandomValues(new Uint8Array(length));
  }

  async hashData(data: string): Promise<string> {
    const encoder = new TextEncoder();
    const encoded = encoder.encode(data);
    const hash = await crypto.subtle.digest('SHA-256', encoded);
    return this.arrayBufferToBase64(hash);
  }

  // Robust base64 encoding/decoding
  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  // Constant-time string comparison for security
  private constantTimeEqual(a: string, b: string): boolean {
    if (a.length !== b.length) return false;

    let result = 0;
    for (let i = 0; i < a.length; i++) {
      result |= a.charCodeAt(i) ^ b.charCodeAt(i);
    }
    return result === 0;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Public API
  // ─────────────────────────────────────────────────────────────────────────

  isEncryptionEnabled(): boolean {
    return this.encryptionEnabled;
  }

  isMessageSigningEnabled(): boolean {
    return this.messageSigningEnabled;
  }

  getSecurityInfo(): {
    encryptionEnabled: boolean;
    encryptionAlgorithm: string | null;
    messageSigningEnabled: boolean;
    signatureAlgorithm: string | null;
    keyRotationInterval: number | null;
    lastKeyRotation: number | null;
    keyExchangeEnabled: boolean;
    backendCompatibilityMode: boolean;
  } {
    return {
      encryptionEnabled: this.encryptionEnabled,
      encryptionAlgorithm: this.encryptionEnabled ? 'AES-GCM-256' : null,
      messageSigningEnabled: this.messageSigningEnabled,
      signatureAlgorithm: this.messageSigningEnabled ? 'HMAC-SHA256' : null,
      keyRotationInterval: this.keyRotationInterval,
      lastKeyRotation: this.lastKeyRotation,
      keyExchangeEnabled: !!this.sessionKeyPair,
      backendCompatibilityMode: this.backendCompatibilityMode,
    };
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Cleanup
  // ─────────────────────────────────────────────────────────────────────────

  destroy(): void {
    // Clear timers
    if (this.keyRotationTimer) {
      clearInterval(this.keyRotationTimer);
      this.keyRotationTimer = null;
    }

    // Clear nonce cache
    this.nonceCache.destroy();

    // Clear IV tracking
    if (this.usedIVs) {
      this.usedIVs.clear();
    }

    // Clear keys from memory
    this.encryptionKey = null;
    this.signingKey = null;
    this.sessionKeyPair = null;
    this.sharedSecret = null;
    this.serverPublicKey = null;

    // Reset state
    this.encryptionEnabled = false;
    this.messageSigningEnabled = false;
    this.keyRotationFailures = 0;

    logger.info('Security manager destroyed, all keys and caches cleared');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Export singleton instance
// ─────────────────────────────────────────────────────────────────────────────

export const securityManager = new SecurityManager();