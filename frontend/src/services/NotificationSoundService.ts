// =============================================================================
// File: src/services/NotificationSoundService.ts
// Description: Global notification sound service for incoming messages
// =============================================================================

import { useAuthStore } from '@/hooks/auth/useAuthStore';
import { logger } from '@/utils/logger';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface NotificationOptions {
  sound?: 'message' | 'mention' | 'call';
  volume?: number;
}

// -----------------------------------------------------------------------------
// Sound URLs
// -----------------------------------------------------------------------------

const SOUNDS = {
  message: '/sounds/notification.mp3',
  mention: '/sounds/notification.mp3',  // Could use different sound
  call: '/sounds/notification.mp3',     // Could use different sound
} as const;

// -----------------------------------------------------------------------------
// Notification Sound Service
// -----------------------------------------------------------------------------

class NotificationSoundService {
  private static instance: NotificationSoundService;
  private audioCache: Map<string, HTMLAudioElement> = new Map();
  private lastPlayTime: number = 0;
  private minInterval: number = 300; // Min 300ms between sounds to prevent spam
  private enabled: boolean = true;
  private volume: number = 0.3;

  private constructor() {
    // Preload sounds
    this.preloadSounds();
  }

  static getInstance(): NotificationSoundService {
    if (!NotificationSoundService.instance) {
      NotificationSoundService.instance = new NotificationSoundService();
    }
    return NotificationSoundService.instance;
  }

  // ---------------------------------------------------------------------------
  // Preload
  // ---------------------------------------------------------------------------

  private preloadSounds(): void {
    Object.entries(SOUNDS).forEach(([key, url]) => {
      try {
        const audio = new Audio(url);
        audio.preload = 'auto';
        audio.volume = this.volume;
        this.audioCache.set(key, audio);
      } catch (error) {
        logger.warn(`Failed to preload sound: ${key}`, error);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Play Sound
  // ---------------------------------------------------------------------------

  play(options: NotificationOptions = {}): void {
    console.log('[NotificationSound] play() called', { enabled: this.enabled, options });
    logger.info('NotificationSound.play() called', { enabled: this.enabled, options });

    if (!this.enabled) {
      console.log('[NotificationSound] disabled, skipping');
      logger.info('NotificationSound: disabled, skipping');
      return;
    }

    const { sound = 'message', volume = this.volume } = options;

    // Throttle to prevent spam
    const now = Date.now();
    if (now - this.lastPlayTime < this.minInterval) {
      logger.info('NotificationSound: throttled');
      return;
    }
    this.lastPlayTime = now;

    try {
      // Get cached audio or create new
      let audio = this.audioCache.get(sound);

      if (!audio) {
        const url = SOUNDS[sound] || SOUNDS.message;
        logger.info('NotificationSound: Creating new Audio', { url });
        audio = new Audio(url);
        this.audioCache.set(sound, audio);
      }

      // Reset and play
      audio.currentTime = 0;
      audio.volume = volume;

      logger.info('NotificationSound: Attempting to play audio...');
      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            logger.info('NotificationSound: Audio played successfully!');
          })
          .catch((error) => {
            // Autoplay was blocked - this is normal on first interaction
            logger.warn('NotificationSound: Blocked by browser:', error.message);
          });
      }
    } catch (error) {
      logger.error('NotificationSound: Failed to play:', error);
    }
  }

  // ---------------------------------------------------------------------------
  // Play for New Message
  // ---------------------------------------------------------------------------

  playForNewMessage(senderId: string | undefined): void {
    // Get current user ID from auth store
    const cachedProfile = useAuthStore.getState().cachedProfile;
    const currentUserId = cachedProfile?.id;

    // DEBUG: Direct console.log to ensure this is called
    console.log('[NotificationSound] playForNewMessage called', {
      senderId,
      currentUserId,
      cachedProfile: cachedProfile ? 'exists' : 'null',
      enabled: this.enabled,
    });

    logger.info('NotificationSound: playForNewMessage called', {
      senderId,
      currentUserId,
      cachedProfile: cachedProfile ? 'exists' : 'null',
      enabled: this.enabled,
    });

    // Don't play sound for own messages
    if (senderId && currentUserId && senderId === currentUserId) {
      logger.info('NotificationSound: Skipping - own message');
      return;
    }

    // Play the notification sound
    logger.info('NotificationSound: Playing sound...');
    this.play({ sound: 'message' });
  }

  // ---------------------------------------------------------------------------
  // Settings
  // ---------------------------------------------------------------------------

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    logger.info(`Notification sounds ${enabled ? 'enabled' : 'disabled'}`);
  }

  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));
    // Update cached audio volumes
    this.audioCache.forEach((audio) => {
      audio.volume = this.volume;
    });
  }

  isEnabled(): boolean {
    return this.enabled;
  }

  getVolume(): number {
    return this.volume;
  }
}

// -----------------------------------------------------------------------------
// Singleton Export
// -----------------------------------------------------------------------------

export const notificationSound = NotificationSoundService.getInstance();

// -----------------------------------------------------------------------------
// Convenience Functions
// -----------------------------------------------------------------------------

export function playMessageSound(senderId?: string): void {
  notificationSound.playForNewMessage(senderId);
}

export function setNotificationSoundEnabled(enabled: boolean): void {
  notificationSound.setEnabled(enabled);
}

export function setNotificationVolume(volume: number): void {
  notificationSound.setVolume(volume);
}
