// =============================================================================
// File: src/wse/handlers/EventHandlers.ts
// Description: Fixed event handlers with proper account filtering
// FIXED: Account filtering by broker connection and proper cleanup
// =============================================================================

import { WSMessage } from '@/wse';
import { useBrokerConnectionStore } from '@/stores/useBrokerConnectionStore';
import { useBrokerAccountStore } from '@/stores/useBrokerAccountStore';
import { useAutomationStore } from '@/stores/useAutomationStore';
import { useSystemStatusStore } from '@/stores/useSystemStatusStore';
import { logger } from '@/wse';
import { BrokerId, BrokerEnvironment } from '@/types/broker.types';
import { AccountData } from '@/api/broker_account';
import { queryClient } from '@/lib/queryClient';
import { queryKeys } from '@/lib/queryKeys';

// Track processed snapshots to prevent duplicates
const processedSnapshots = {
  broker: new Map<string, number>(),
  account: new Map<string, number>(),
};

// Clean old snapshots after 5 minutes
const SNAPSHOT_CACHE_TIME = 5 * 60 * 1000;

function cleanOldSnapshots() {
  const now = Date.now();
  for (const [id, timestamp] of processedSnapshots.broker.entries()) {
    if (now - timestamp > SNAPSHOT_CACHE_TIME) {
      processedSnapshots.broker.delete(id);
    }
  }
  for (const [id, timestamp] of processedSnapshots.account.entries()) {
    if (now - timestamp > SNAPSHOT_CACHE_TIME) {
      processedSnapshots.account.delete(id);
    }
  }
}

// Run cleanup every minute
setInterval(cleanOldSnapshots, 60000);

export class EventHandlers {

  // ─────────────────────────────────────────────────────────────────────────
  // Broker Connection Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleBrokerConnectionUpdate(message: WSMessage): void {
    try {
      const update = message.p;
      const brokerStore = useBrokerConnectionStore.getState();
      const accountStore = useBrokerAccountStore.getState();

      // Validate virtual broker environment
      if (update.broker_id === 'virtual' && update.environment !== 'paper') {
        logger.warn('Virtual broker update with non-sim environment, forcing to paper');
        update.environment = 'paper';
      }

      logger.info('=== BROKER CONNECTION UPDATE ===');
      logger.info('Update details:', {
        broker_id: update.broker_id,
        environment: update.environment,
        status: update.status,
        connected: update.connected,
        is_healthy: update.is_healthy,
        message: update.message,
        broker_connection_id: update.broker_connection_id,
      });

      // CRITICAL FIX (Nov 15, 2025): Handle DISCONNECTED/REMOVED status BEFORE mapping
      // Backend sends {status: 'DISCONNECTED', connected: false} when user clicks Disconnect
      // We should REMOVE the card immediately, NOT map it to 'error' status
      const statusStr = String(update.status || '').toUpperCase();

      // CRITICAL FIX: Ignore CONNECTING status during OAuth flow
      // Problem: Backend sends CONNECTING update → card appears BEFORE OAuth redirect
      // Solution: Only show card after CONNECTED status (after OAuth callback completes)
      const isOAuthBroker = update.broker_id === 'alpaca' || update.broker_id === 'tradestation';
      const isConnectingStatus = statusStr === 'CONNECTING' || statusStr === 'PENDING' || statusStr === 'INITIALIZING';

      if (isOAuthBroker && isConnectingStatus && !update.connected) {
        logger.info(`[EventHandlers] Ignoring CONNECTING status for OAuth broker ${update.broker_id} (will show after OAuth completes)`);
        return; // Don't process CONNECTING updates for OAuth brokers
      }
      if (statusStr === 'DISCONNECTED' || statusStr === 'REMOVED') {
        logger.info(`DISCONNECTED status received - removing broker ${update.broker_id}:${update.environment}`);
        brokerStore.removeConnection(
          update.broker_id,
          update.environment.toLowerCase() as BrokerEnvironment
        );

        // Also clean up accounts
        logger.info(`[EventHandlers] Broker ${update.broker_id}:${update.environment} disconnected, cleaning up accounts`);
        const accounts = accountStore.getAccountsByBroker(update.broker_id).filter(
          (acc: AccountData) => acc.environment === update.environment
        );
        if (accounts.length > 0) {
          accountStore.removeAccountsByBroker(
            update.broker_id,
            update.environment.toLowerCase() as BrokerEnvironment
          );
          logger.info('Accounts removed from cache for disconnected broker (no REST API call)');
        }

        return; // Early exit - don't process further
      }

      // Map the real-time update to our status
      let mappedStatus: 'connecting' | 'connected' | 'error' = 'error';

      // statusStr already defined above (line 75)
      if (update.connected === true || update.is_healthy === true) {
        mappedStatus = 'connected';
      } else if (statusStr === 'CONNECTED' || statusStr === 'HEALTHY' || statusStr === 'ACTIVE') {
        mappedStatus = 'connected';
      } else if (statusStr === 'CONNECTING' || statusStr === 'PENDING' || statusStr === 'INITIALIZING' ||
                 statusStr === 'AUTHENTICATING' || statusStr === 'GETTING_DATA' || statusStr === 'LOADING_ACCOUNTS') {
        mappedStatus = 'connecting';
      } else if (update.status?.toLowerCase() === 'connected' || update.status?.toLowerCase() === 'healthy') {
        mappedStatus = 'connected';
      } else if (update.status?.toLowerCase() === 'connecting' || update.status?.toLowerCase() === 'pending') {
        mappedStatus = 'connecting';
      }

      // FIXED (Nov 11, 2025): Trust backend connected status
      // REMOVED account-based status downgrade that caused 30-60s "connecting" hang
      // Backend saga sets connected=true after successful authentication
      // Accounts will appear shortly after via separate broker_account_snapshot events
      // No need to artificially delay "connected" status waiting for accounts

      const connectionUpdate = {
        broker_id: update.broker_id,
        environment: update.environment,
        status: mappedStatus,
        connected: mappedStatus === 'connected',
        is_healthy: mappedStatus === 'connected',
        message: update.message || update.error_message,
        broker_connection_id: update.broker_connection_id,
        timestamp: new Date().toISOString()
      };

      // Process the real-time update
      const processed = brokerStore.processRealtimeUpdate(connectionUpdate);

      if (processed) {
        if (mappedStatus === 'connected') {
          brokerStore.clearOptimisticStatus(update.broker_id, update.environment);
        }

        // BEST PRACTICE (TkDodo 2025): WebSocket → invalidateQueries (simpler, more reliable)
        // TkDodo: "Prioritize invalidation over direct updates for most use cases"
        // Incremental updates → let React Query refetch (only if component is observing)
        queryClient.invalidateQueries({
          queryKey: queryKeys.brokers.connections(),
          refetchType: 'active' // Only refetch if query is active
        });

        // Dispatch event for UI components
        window.dispatchEvent(new CustomEvent('brokerConnectionUpdated', {
          detail: connectionUpdate
        }));

        logger.info('Broker connection update processed successfully');
      }

      // CRITICAL FIX (Nov 17, 2025): Only clean up accounts if ACTUALLY disconnected
      // BUG: connected=false also triggers during CONNECTING state, deleting accounts prematurely
      // FIX: Check mappedStatus explicitly to avoid cleaning during connection establishment
      if (mappedStatus === 'error' || mappedStatus === 'disconnected') {
        logger.info(`[EventHandlers] Broker ${update.broker_id}:${update.environment} disconnected (status=${mappedStatus}), cleaning up accounts`);

        // BEST PRACTICE (TkDodo 2025): WebSocket disconnect → setQueryData (no REST API call)
        // Remove accounts for disconnected broker directly from cache (immutable)
        // Why: Optimistic UI update without waiting for REST API call
        queryClient.setQueryData(queryKeys.accounts.all, (old: any[] | undefined) => {
          if (!old) return [];
          // Filter out accounts for disconnected broker
          return old.filter((acc: any) =>
            !(acc.broker === update.broker_id && acc.environment === update.environment)
          );
        });
        logger.info('Accounts removed from cache for disconnected broker (no REST API call)');

        // Dispatch event to remove accounts
        window.dispatchEvent(new CustomEvent('brokerAccountsDeleted', {
          detail: {
            broker_id: update.broker_id,
            environment: update.environment,
            broker_connection_id: update.broker_connection_id,
            reason: 'Broker disconnected'
          }
        }));
      }
    } catch (error) {
      logger.error('Error handling broker connection update:', error);
    }
  }

  static handleBrokerDisconnected(message: WSMessage): void {
    try {
      const update = message.p;
      const brokerStore = useBrokerConnectionStore.getState();
      const accountStore = useBrokerAccountStore.getState();

      logger.info('=== BROKER DISCONNECTED EVENT RECEIVED ===');
      logger.info('Disconnect details:', {
        broker_id: update.broker_id,
        environment: update.environment,
        reason: update.reason,
        broker_connection_id: update.broker_connection_id,
        timestamp: update.timestamp
      });

      // Validate virtual broker environment
      if (update.broker_id === 'virtual' && update.environment !== 'paper') {
        logger.warn('Virtual broker disconnect with non-paper environment, forcing to paper');
        update.environment = 'paper';
      }

      // IMMEDIATELY remove the broker connection from UI
      logger.info(`Removing broker ${update.broker_id}:${update.environment} from UI`);
      brokerStore.removeConnection(
        update.broker_id,
        update.environment.toLowerCase() as BrokerEnvironment
      );

      // CRITICAL FIX: IMMEDIATELY remove accounts from React Query cache (optimistic removal)
      // TkDodo: Use setQueryData for instant UI update, then invalidate for consistency
      const beforeCount = queryClient.getQueryData<any[]>(queryKeys.accounts.all)?.length || 0;

      queryClient.setQueryData(queryKeys.accounts.all, (old: any[] | undefined) => {
        if (!old) {
          console.log('[EventHandlers] No accounts in cache to remove');
          return [];
        }

        console.log('[EventHandlers] BEFORE filter - accounts:', old.map(a => `${a.broker}:${a.environment}:${a.accountId}`));
        console.log('[EventHandlers] Filtering broker:', update.broker_id, 'environment:', update.environment);

        // Filter out all accounts for this broker (case-insensitive)
        const filtered = old.filter((acc: any) => {
          const brokerMatch = acc.broker?.toLowerCase() === update.broker_id?.toLowerCase();
          const envMatch = acc.environment?.toLowerCase() === update.environment?.toLowerCase();
          const shouldRemove = brokerMatch && envMatch;

          if (shouldRemove) {
            console.log('[EventHandlers] REMOVING account:', acc.accountId, acc.broker, acc.environment);
          }

          return !shouldRemove;
        });

        console.log('[EventHandlers] AFTER filter - accounts:', filtered.map(a => `${a.broker}:${a.environment}:${a.accountId}`));
        return filtered;
      });

      const afterCount = queryClient.getQueryData<any[]>(queryKeys.accounts.all)?.length || 0;
      logger.info(`Accounts removed: ${beforeCount} -> ${afterCount} for ${update.broker_id}:${update.environment}`);

      // CRITICAL FIX: Invalidate React Query cache for broker connections
      // TkDodo Best Practice: Invalidate queries after state changes for consistency
      queryClient.invalidateQueries({ queryKey: queryKeys.brokers.connections() });
      // REMOVED (Nov 17, 2025): accounts.all invalidation redundant (setQueryData on line 234 already updated)

      // Remove from Zustand store (legacy, may remove later)
      const accounts = accountStore.getAccountsByBroker(update.broker_id).filter(
        (acc: AccountData) => acc.environment === update.environment
      );

      if (accounts.length > 0) {
        accountStore.removeAccountsByBroker(
          update.broker_id,
          update.environment.toLowerCase() as BrokerEnvironment
        );
      }

      // Dispatch events for UI components
      window.dispatchEvent(new CustomEvent('brokerDisconnected', {
        detail: {
          broker_id: update.broker_id,
          environment: update.environment,
          reason: update.reason,
          timestamp: update.timestamp || new Date().toISOString()
        }
      }));

      // Also dispatch account deletion event
      window.dispatchEvent(new CustomEvent('brokerAccountsDeleted', {
        detail: {
          broker_id: update.broker_id,
          environment: update.environment,
          broker_connection_id: update.broker_connection_id,
          reason: 'Broker disconnected'
        }
      }));

      logger.info(`Broker ${update.broker_id}:${update.environment} successfully removed from UI`);
    } catch (error) {
      logger.error('Error handling broker disconnected event:', error);
    }
  }

  static handleBrokerConnectionEstablished(message: WSMessage): void {
    try {
      const update = message.p;
      const brokerStore = useBrokerConnectionStore.getState();

      logger.info('=== BROKER CONNECTION ESTABLISHED EVENT RECEIVED ===');
      logger.info('Connection details:', {
        broker_id: update.broker_id,
        environment: update.environment,
        broker_connection_id: update.broker_connection_id,
        status: update.status,
        api_endpoint: update.api_endpoint,
        timestamp: update.timestamp
      });

      // Validate virtual broker environment
      if (update.broker_id === 'virtual' && update.environment !== 'paper') {
        logger.warn('Virtual broker connection established with non-paper environment, forcing to paper');
        update.environment = 'paper';
      }

      // IMMEDIATELY update the broker connection status to "connected"
      logger.info(`Updating broker ${update.broker_id}:${update.environment} to CONNECTED status`);
      brokerStore.updateConnection({
        id: update.broker_id as any,
        environment: update.environment.toLowerCase() as BrokerEnvironment,
        status: 'connected',
        lastUpdate: Date.now()
      });

      // CRITICAL FIX (Nov 12, 2025): Request account snapshot immediately after connection
      // Problem: Accounts created in ~2s but frontend waits 60s for individual account_update events
      // Root Cause: Relying on individual BrokerAccountLinked events from saga causes delay
      // Solution: Request account snapshot immediately to get all accounts at once
      // This matches TkDodo pattern: WebSocket snapshot → setQueryData (no REST API delay)
      logger.info('[INSTANT ACCOUNT LOAD] Requesting account snapshot after broker connection');
      const wseConnection = (window as any).__WSE_CONNECTION__;
      if (wseConnection && typeof wseConnection.sendMessage === 'function') {
        wseConnection.sendMessage({
          t: 'sync_request',
          p: {
            topics: ['broker_account_events'],
            include_snapshots: true,
            timestamp: new Date().toISOString()
          }
        });
        logger.info('[INSTANT ACCOUNT LOAD] Account snapshot request sent');
      } else {
        logger.warn('[INSTANT ACCOUNT LOAD] WSE connection not available, cannot request snapshot');
      }

      // Dispatch event for UI components
      window.dispatchEvent(new CustomEvent('brokerConnected', {
        detail: {
          brokerId: update.broker_id,
          environment: update.environment,
          brokerConnectionId: update.broker_connection_id,
          timestamp: update.timestamp
        }
      }));

      logger.info(`Broker ${update.broker_id}:${update.environment} successfully marked as CONNECTED`);
    } catch (error) {
      logger.error('Error handling broker connection established event:', error);
    }
  }

  static handleBrokerConnectionSnapshot(message: WSMessage): void {
    try {
      const payload = message.p;
      const brokerStore = useBrokerConnectionStore.getState();

      logger.info('=== BROKER STATUS SNAPSHOT RECEIVED ===');
      logger.info('Snapshot details:', {
        connectionsCount: payload.connections?.length || 0,
        trimArchived: payload.trim_archived,
        includeModuleDetails: payload.include_module_details,
        onlyConnected: payload.only_connected
      });

      // FIX (Nov 9, 2025): Only deduplicate if backend provides unique ID
      // Previously used timestamp fallback which caused collisions and skipped valid snapshots
      // This was causing "Disconnect button reappears" issue
      const snapshotId = message.id;

      if (snapshotId) {
        // We have a real unique ID from backend
        if (processedSnapshots.broker.has(snapshotId)) {
          logger.info('Ignoring duplicate broker snapshot:', snapshotId);
          return;
        }
        // Mark as processed
        processedSnapshots.broker.set(snapshotId, Date.now());
      } else {
        // No unique ID - process anyway but log warning
        logger.warn('Snapshot missing unique ID, processing anyway (may cause duplicates)');
      }

      const connections = payload.connections || [];

      if (!Array.isArray(connections)) {
        logger.error('Invalid broker snapshot format - connections is not an array:', payload);
        return;
      }

      logger.info(`Processing ${connections.length} broker connections from snapshot`);

      // Map connections to the store format
      const mappedConnections = connections.map((broker: any) => {
        if (broker.broker_id === 'virtual' && broker.environment !== 'paper') {
          broker.environment = 'paper';
        }

        const status = mapSnapshotStatus(broker);

        return {
          id: broker.broker_id as BrokerId,
          environment: broker.environment.toLowerCase() as BrokerEnvironment,
          status: status,
          errorMessage: formatSnapshotError(broker),
          lastUpdate: Date.now(),
          brokerConnectionId: broker.broker_connection_id || broker.id,
          apiEndpoint: broker.api_endpoint
        };
      });

      // Use the store's snapshot method
      // NOTE: Use merge mode (replace=false) to preserve optimistic UI updates during disconnect
      brokerStore.setSnapshot(mappedConnections);

      // Dispatch event for UI components
      window.dispatchEvent(new CustomEvent('brokerSnapshotReceived', {
        detail: {
          connections: mappedConnections,
          count: mappedConnections.length,
          timestamp: new Date().toISOString()
        }
      }));

      // REMOVED: Early account snapshot request
      // Account snapshot will be sent automatically by backend when saga completes
      // This prevents race condition where snapshot is requested before accounts are in DB
      logger.info('Broker snapshot complete, waiting for saga to send account snapshot');

      logger.info('Broker snapshot processing complete');
    } catch (error) {
      logger.error('Error handling broker status snapshot:', error);
    }
  }

  static handleBrokerStatusRemove(message: WSMessage): void {
    try {
      const payload = message.p;
      const brokerStore = useBrokerConnectionStore.getState();

      logger.info('Broker status remove received:', payload);

      // Remove from the store
      brokerStore.removeConnection(payload.broker_id, payload.environment);

      // Notify UI with explicit removal flag
      window.dispatchEvent(new CustomEvent('brokerRemoved', {
        detail: {
          broker_id: payload.broker_id,
          environment: payload.environment,
          reason: payload.reason || 'Connection removed',
          explicit_removal: true,
          user_initiated: true
        }
      }));
    } catch (error) {
      logger.error('Error handling broker status remove:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Account Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleAccountUpdate(message: WSMessage): void {
    try {
      const update = message.p;
      const accountStore = useBrokerAccountStore.getState();
      const brokerStore = useBrokerConnectionStore.getState();

      logger.info('Account update received:', update);

      // Validate that the broker is connected
      const brokerId = update.brokerId || update.broker_id;
      if (!brokerId) {
        logger.error('[EventHandlers] Account update missing brokerId/broker_id', { update });
        return;
      }

      const environment = (update.environment || 'paper').toLowerCase();
      // CRITICAL FIX (Nov 16, 2025): Make validation more lenient for ALL brokers
      // Accept both 'connected' and 'connecting' states (case-insensitive)
      // This handles the race condition where accounts arrive before connection is fully established
      const connectionExists = brokerStore.connections.some(
        c => c.id.toLowerCase() === brokerId.toLowerCase() &&
             c.environment.toLowerCase() === environment
      );

      const isConnectedOrConnecting = brokerStore.connections.some(
        c => c.id.toLowerCase() === brokerId.toLowerCase() &&
             c.environment.toLowerCase() === environment &&
             (c.status?.toLowerCase() === 'connected' || c.status?.toLowerCase() === 'connecting')
      );

      // If connection doesn't exist at all, skip the update
      if (!connectionExists) {
        logger.warn(`Ignoring account update for unknown broker ${brokerId}:${environment} (connection not found)`);
        return;
      }

      // If connection exists but not connected/connecting, log but process anyway (race condition tolerance)
      if (!isConnectedOrConnecting) {
        logger.info(
          `Processing account update for broker ${brokerId}:${environment} despite status not being connected/connecting ` +
          `(race condition tolerance for ALL brokers)`
        );
      }

      // Map to AccountData format
      const mappedAccount = {
        accountId: update.accountId || update.account_id || update.id,
        brokerAccountId: update.brokerAccountId || update.broker_account_id,
        accountName: update.accountName || update.account_name,
        assetType: update.assetType || update.asset_type || 'stocks',
        accountType: update.accountType || update.account_type,
        balance: update.balance || '0',
        currency: update.currency || 'USD',
        equity: update.equity,
        buyingPower: update.buyingPower || update.buying_power,
        status: update.status || 'active',
        environment: environment as 'paper' | 'live',
        broker: brokerId,
        positions: update.positions || [],
        openOrdersCount: update.openOrdersCount || update.open_orders_count || 0,
        dailyPnl: update.dailyPnl || update.daily_pnl,
        dailyPnlPercent: update.dailyPnlPercent || update.daily_pnl_percent,
        brokerConnectionId: update.brokerConnectionId || update.broker_connection_id,
      };

      // BEST PRACTICE (TkDodo 2025): WebSocket → setQueryData for high-frequency updates
      // TkDodo: "For frequent, granular updates (balance changes), use setQueryData"
      // Account balance updates are high-frequency → use setQueryData (no REST call)
      queryClient.setQueryData(queryKeys.accounts.all, (old: any[] | undefined) => {
        if (!old) return [mappedAccount];

        const accountId = mappedAccount.accountId;
        const index = old.findIndex((a: any) => a.accountId === accountId);

        if (index >= 0) {
          // Update existing account (immutable)
          return old.map((a, i) => (i === index ? { ...a, ...mappedAccount } : a));
        }

        // Add new account
        return [...old, mappedAccount];
      });
      logger.info('Account cache updated directly from WebSocket (no REST API call)');

      // REMOVED (Nov 17, 2025): Redundant invalidateQueries causes flashing bug
      // setQueryData already notifies observers (React Query best practice)
      // Extra invalidation triggered double re-renders, causing "flashing" when incremental updates race with snapshots
      logger.info('Account cache updated (observers auto-notified by setQueryData)');

      // Dispatch event for UI components (legacy, may remove later)
      window.dispatchEvent(new CustomEvent('accountUpdated', {
        detail: mappedAccount
      }));
    } catch (error) {
      logger.error('Error handling account update:', error);
    }
  }

  static handleAccountRemove(message: WSMessage): void {
    try {
      const payload = message.p;
      const accountStore = useBrokerAccountStore.getState();

      logger.info('=== ACCOUNT REMOVE ===');
      logger.info('Payload:', payload);
      logger.info('Deletion type:', payload.deletion_type || 'unknown');
      logger.info('Cascade:', payload.cascade || false);

      const accountId = payload.accountId || payload.account_id || payload.id;
      accountStore.removeAccount(accountId);

      // Dispatch detailed event with enhanced metadata
      window.dispatchEvent(new CustomEvent('accountRemoved', {
        detail: {
          account_id: accountId,
          broker_id: payload.broker_id,
          broker_account_id: payload.broker_account_id,
          broker_connection_id: payload.broker_connection_id,
          environment: payload.environment,
          reason: payload.reason || 'Account deleted',
          deletion_type: payload.deletion_type || 'hard',
          cascade: payload.cascade || false,
          deleted_at: payload.deleted_at
        }
      }));

      logger.info(`✓ Account ${accountId} removed (${payload.deletion_type || 'hard'} delete)`);
    } catch (error) {
      logger.error('Error handling account remove:', error);
    }
  }

  static handleAccountsBulkRemove(message: WSMessage): void {
    try {
      const payload = message.p;
      const accountStore = useBrokerAccountStore.getState();

      logger.info('=== ACCOUNTS BULK REMOVE ===');
      logger.info('Broker ID:', payload.broker_id);
      logger.info('Environment:', payload.environment);
      logger.info('Reason:', payload.reason);

      // Remove by broker connection ID if provided
      if (payload.broker_connection_id) {
        const removedCount = accountStore.removeAccountsByBrokerConnection(payload.broker_connection_id);

        logger.info(`✓ Removed ${removedCount} accounts for broker connection ${payload.broker_connection_id}`);

        window.dispatchEvent(new CustomEvent('brokerAccountsDeleted', {
          detail: {
            broker_connection_id: payload.broker_connection_id,
            broker_id: payload.broker_id,
            environment: payload.environment,
            count: payload.count || removedCount || 0,
            reason: payload.reason || 'Broker disconnected',
            cascade: true
          }
        }));
      }
      // Fallback: remove by broker_id and environment
      else if (payload.broker_id && payload.environment) {
        const accountsToRemove = accountStore.getAccountsByBroker(payload.broker_id)
          .filter((acc: any) => acc.environment === payload.environment);

        accountsToRemove.forEach((acc: any) => accountStore.removeAccount(acc.accountId));

        logger.info(`✓ Removed ${accountsToRemove.length} accounts for ${payload.broker_id}:${payload.environment}`);

        window.dispatchEvent(new CustomEvent('brokerAccountsDeleted', {
          detail: {
            broker_id: payload.broker_id,
            environment: payload.environment,
            count: accountsToRemove.length,
            reason: payload.reason || 'Broker disconnected',
            cascade: true
          }
        }));
      }
    } catch (error) {
      logger.error('Error handling accounts bulk remove:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Account Snapshot Event
  // ─────────────────────────────────────────────────────────────────────────

  static handleBrokerAccountSnapshot(message: WSMessage): void {
    try {
      const payload = message.p;
      const accountStore = useBrokerAccountStore.getState();
      const brokerStore = useBrokerConnectionStore.getState();

      logger.info('=== ACCOUNT SNAPSHOT RECEIVED ===');
      logger.info('Accounts count:', payload.accounts?.length || 0);

      // Check if we've already processed this snapshot
      const snapshotId = message.id || `${payload.timestamp}_${payload.count}`;
      if (processedSnapshots.account.has(snapshotId)) {
        logger.info('Ignoring duplicate account snapshot:', snapshotId);
        return;
      }

      // Mark as processed
      processedSnapshots.account.set(snapshotId, Date.now());

      if (!payload.accounts || !Array.isArray(payload.accounts)) {
        logger.error('Invalid account snapshot format - accounts is not an array:', payload);
        return;
      }

      logger.info(`Processing ${payload.accounts.length} accounts from snapshot`);

      // CRITICAL DEBUG: Log received accounts BEFORE filtering
      logger.info('[CRITICAL] Received account IDs from backend:', payload.accounts.map((a: any) => a.accountId || a.broker_account_id));
      logger.info('[CRITICAL] Received account brokers:', payload.accounts.map((a: any) => `${a.brokerId || a.broker_id}:${a.environment}`));

      // Get connected brokers for filtering
      logger.info('[CRITICAL] Total brokers in store:', brokerStore.connections.length);
      logger.info('[CRITICAL] Broker connection statuses:', brokerStore.connections.map(c => ({id: c.id, env: c.environment, status: c.status})));

      // CRITICAL FIX: Check sessionStorage for user-disconnected brokers
      // Don't include accounts from brokers that user explicitly disconnected
      const userDisconnectedBrokers = new Set<string>();
      try {
        Object.keys(sessionStorage).forEach(key => {
          if (key.startsWith('broker_disconnected_')) {
            const brokerKey = key.replace('broker_disconnected_', '');
            userDisconnectedBrokers.add(brokerKey);
            logger.info(`[CRITICAL] User disconnected: ${brokerKey} (ignoring accounts)`);
          }
        });
      } catch (e) {
        logger.error('[EventHandlers] Error reading sessionStorage:', e);
      }

      const connectedBrokers = new Set(
        brokerStore.connections
          .filter(c => c.status === 'connected')
          .map(c => `${c.id.toLowerCase()}_${c.environment.toLowerCase()}`)
      );

      logger.info('[CRITICAL] Connected broker keys for filtering:', Array.from(connectedBrokers));
      logger.info('[CRITICAL] User-disconnected broker keys:', Array.from(userDisconnectedBrokers));

      // Map and filter accounts
      const mappedAccounts = payload.accounts
        .map((account: any) => ({
          accountId: account.accountId || account.account_id || account.id,
          brokerAccountId: account.brokerAccountId || account.broker_account_id,
          accountName: account.accountName || account.account_name,
          assetType: account.assetType || account.asset_type || 'stocks',
          accountType: account.accountType || account.account_type,
          balance: account.balance || '0',
          currency: account.currency || 'USD',
          equity: account.equity,
          buyingPower: account.buyingPower || account.buying_power,
          status: account.status || 'active',
          environment: (account.environment || 'paper').toLowerCase() as 'paper' | 'live',
          broker: account.brokerId || account.broker_id,
          positions: account.positions || [],
          openOrdersCount: account.openOrdersCount || account.open_orders_count || 0,
          dailyPnl: account.dailyPnl || account.daily_pnl,
          dailyPnlPercent: account.dailyPnlPercent || account.daily_pnl_percent,
          brokerConnectionId: account.brokerConnectionId || account.broker_connection_id,
        }))
        .filter((account: AccountData) => {
          const brokerKey = `${account.broker.toLowerCase()}_${account.environment.toLowerCase()}`;

          // CRITICAL FIX: Reject accounts from user-disconnected brokers
          // Problem: Snapshots arrive AFTER disconnect and re-add accounts
          // Solution: Check sessionStorage tracking and skip user-disconnected brokers
          //
          // DEFENSIVE CHECK (Nov 2025): If broker IS connected in store,
          // ignore stale sessionStorage flag (React batching race condition)
          const isInConnectedSet = connectedBrokers.has(brokerKey);

          if (userDisconnectedBrokers.has(brokerKey)) {
            // CRITICAL: Check if broker is NOW connected (reconnect case)
            if (isInConnectedSet) {
              logger.info(
                `[EventHandlers] Broker ${brokerKey} IS CONNECTED despite sessionStorage flag - ` +
                `allowing account (race condition - flag not cleared yet)`
              );
              // Allow account - broker is connected, sessionStorage is stale
            } else {
              // Broker is NOT connected - sessionStorage is correct
              logger.info(
                `[EventHandlers] REJECTING account ${account.accountId} - broker ${brokerKey} was disconnected by user`
              );
              return false; // Don't include accounts from disconnected brokers
            }
          }

          if (!isInConnectedSet) {
            // Log but include anyway - backend wouldn't send if not valid
            logger.info(
              `[EventHandlers] Account ${account.accountId} from broker ${brokerKey} not in connectedBrokers set. ` +
              `Including anyway (race condition tolerance for ALL brokers)`
            );
          }

          return true; // Include all accounts from snapshot (except user-disconnected)
        });

      // Use the snapshot method
      accountStore.setAccountsSnapshot(mappedAccounts);

      // BEST PRACTICE (TkDodo 2025): WebSocket snapshot → setQueryData (no REST API call)
      // This ensures UI updates INSTANTLY when new accounts arrive via WebSocket snapshot
      // Problem: VB accounts created at T+1s, snapshot arrives at T+2s, but UI waited 30-60s
      // Solution: Use setQueryData to update cache directly with snapshot data (no refetch needed)
      // Why: WebSocket already delivered fresh data - no need for REST API roundtrip
      queryClient.setQueryData(queryKeys.accounts.all, mappedAccounts);
      logger.info('Account cache updated directly from WebSocket snapshot (no REST API call)');

      // REMOVED (Nov 17, 2025): Redundant invalidation - setQueryData notifies observers automatically
      // TkDodo: "setQueryData already triggers re-renders in React Query v4+"
      // Previous code caused double re-renders (flashing bug)
      logger.info('Account snapshot applied (observers auto-notified by setQueryData)');

      // Dispatch success event
      window.dispatchEvent(new CustomEvent('accountSnapshotReceived', {
        detail: {
          accounts: mappedAccounts,
          count: mappedAccounts.length,
          timestamp: new Date().toISOString()
        }
      }));

      logger.info(`Account snapshot processing complete: ${mappedAccounts.length} accounts set`);
    } catch (error) {
      logger.error('Error handling account snapshot:', error);

      window.dispatchEvent(new CustomEvent('accountSnapshotError', {
        detail: {
          error: error instanceof Error ? error.message : String(error),
          timestamp: new Date().toISOString()
        }
      }));
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Automation Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleAutomationUpdate(message: WSMessage): void {
    try {
      const update = message.p;
      const automationStore = useAutomationStore.getState();

      logger.info('Automation update received:', update);

      const automationId = update.automation_id || update.id;

      if (!automationId) {
        logger.error('Automation update missing automation_id:', update);
        return;
      }

      const existingAutomation = automationStore.getAutomationById(automationId);

      const automationUpdate: any = {
        automation_id: automationId,
        name: update.name,
        account_id: update.account_id,
        broker_id: update.broker_id,
        environment: update.environment,
        asset_type: update.asset_type,
        settings: update.settings || update.parameters || (existingAutomation?.settings || {}),
        active: update.active !== undefined ? update.active : (existingAutomation?.active || false),
        webhook_generated: update.webhook_generated !== undefined ? update.webhook_generated : (existingAutomation?.webhook_generated || false),
        status: update.status,
        last_execution: update.last_execution,
        next_execution: update.next_execution,
        error_message: update.error_message,
        created_at: update.created_at || existingAutomation?.created_at,
        updated_at: update.updated_at || new Date().toISOString(),
      };

      if (!existingAutomation) {
        automationUpdate.name = automationUpdate.name || 'Unnamed Automation';
        automationUpdate.settings = automationUpdate.settings || {};
        automationUpdate.active = automationUpdate.active || false;
        automationUpdate.webhook_generated = automationUpdate.webhook_generated || false;
      }

      automationStore.updateAutomation(automationUpdate);

      switch (update.status) {
        case 'running':
          logger.info(`Automation ${automationUpdate.name} is now running`);
          break;
        case 'stopped':
          logger.info(`Automation ${automationUpdate.name} has been stopped`);
          break;
        case 'error':
          logger.error(`Automation ${automationUpdate.name} encountered an error: ${update.error_message}`);
          break;
      }

      window.dispatchEvent(new CustomEvent('automationUpdate', {
        detail: automationUpdate
      }));
    } catch (error) {
      logger.error('Error handling automation update:', error);
    }
  }

  static handleAutomationSnapshot(message: WSMessage): void {
    try {
      const payload = message.p;
      const automationStore = useAutomationStore.getState();

      logger.info('=== AUTOMATION SNAPSHOT RECEIVED ===');
      logger.info('Automations count:', payload.automations?.length || 0);

      if (!payload.automations || !Array.isArray(payload.automations)) {
        logger.error('Invalid automation snapshot format');
        return;
      }

      const mappedAutomations = payload.automations.map((automation: any) => ({
        automation_id: automation.automation_id || automation.id,
        name: automation.name || 'Unnamed Automation',
        account_id: automation.account_id,
        broker_id: automation.broker_id,
        environment: automation.environment,
        asset_type: automation.asset_type,
        settings: automation.settings || automation.parameters || {},
        active: automation.active || false,
        webhook_generated: automation.webhook_generated || false,
        status: automation.status,
        last_execution: automation.last_execution,
        next_execution: automation.next_execution,
        error_message: automation.error_message,
        created_at: automation.created_at,
        updated_at: automation.updated_at,
      }));

      automationStore.setAutomations(mappedAutomations);

      window.dispatchEvent(new CustomEvent('automationSnapshotReceived', {
        detail: {
          automations: mappedAutomations,
          count: mappedAutomations.length,
          timestamp: new Date().toISOString()
        }
      }));

      logger.info('Automation snapshot processing complete');
    } catch (error) {
      logger.error('Error handling automation snapshot:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Trading Events - Positions
  // ─────────────────────────────────────────────────────────────────────────

  static handlePositionUpdate(message: WSMessage): void {
    try {
      const position = message.p;
      const accountStore = useBrokerAccountStore.getState();

      logger.info('Position update received:', position);

      const account = accountStore.accounts.find(
        acc => acc.accountId === position.account_id
      );

      if (account) {
        const updatedPositions = account.positions || [];
        const existingIndex = updatedPositions.findIndex(
          p => p.symbol === position.symbol
        );

        if (existingIndex >= 0) {
          updatedPositions[existingIndex] = {
            symbol: position.symbol,
            quantity: position.quantity,
            side: position.side,
            market_value: position.market_value,
            avg_cost: position.avg_cost,
            unrealized_pnl: position.unrealized_pnl,
            unrealized_pnl_percent: position.unrealized_pnl_percent,
            asset_class: position.asset_class,
          };
        } else {
          updatedPositions.push({
            symbol: position.symbol,
            quantity: position.quantity,
            side: position.side,
            market_value: position.market_value,
            avg_cost: position.avg_cost,
            unrealized_pnl: position.unrealized_pnl,
            unrealized_pnl_percent: position.unrealized_pnl_percent,
            asset_class: position.asset_class,
          });
        }

        accountStore.updateAccount({
          ...account,
          positions: updatedPositions,
        });
      }

      window.dispatchEvent(new CustomEvent('positionUpdate', {
        detail: position
      }));
    } catch (error) {
      logger.error('Error handling position update:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Trading Events - Orders
  // ─────────────────────────────────────────────────────────────────────────

  static handleOrderUpdate(message: WSMessage): void {
    try {
      const order = message.p;

      logger.info('Order update received:', order);

      // BEST PRACTICE (TkDodo 2025): WebSocket → invalidateQueries (simpler, more reliable)
      // Orders are not high-frequency enough to justify setQueryData complexity
      queryClient.invalidateQueries({
        queryKey: queryKeys.orders.all,
        refetchType: 'active'
      });
      logger.info('Order cache invalidated from WebSocket');

      // Dispatch custom events for specific status changes
      const eventType = order.status === 'filled' ? 'orderFilled' :
                       order.status === 'partially_filled' ? 'orderPartiallyFilled' :
                       order.status === 'cancelled' ? 'orderCancelled' :
                       order.status === 'rejected' ? 'orderRejected' :
                       'orderUpdate';

      window.dispatchEvent(new CustomEvent(eventType, {
        detail: {
          order_id: order.order_id,
          client_order_id: order.client_order_id,
          account_id: order.account_id,
          automation_id: order.automation_id,
          broker_order_id: order.broker_order_id,
          symbol: order.symbol,
          side: order.side,
          quantity: order.quantity,
          order_type: order.order_type,
          status: order.status,
          filled_quantity: order.filled_quantity,
          remaining_quantity: order.remaining_quantity,
          avg_fill_price: order.avg_fill_price,
          limit_price: order.limit_price,
          stop_price: order.stop_price,
          time_in_force: order.time_in_force,
          asset_type: order.asset_type,
          bracket_group_id: order.bracket_group_id,
          bracket_type: order.bracket_type,
          total_commission: order.total_commission,
          total_fees: order.total_fees,
          created_at: order.created_at,
          submitted_at: order.submitted_at,
          accepted_at: order.accepted_at,
          filled_at: order.filled_at,
          cancelled_at: order.cancelled_at,
          rejected_at: order.rejected_at,
          updated_at: order.updated_at,
          reject_reason: order.reject_reason,
        }
      }));

      switch (order.status) {
        case 'filled':
          logger.info(`Order ${order.order_id} filled: ${order.filled_quantity} ${order.symbol} @ ${order.avg_fill_price}`);
          break;
        case 'rejected':
          logger.error(`Order ${order.order_id} rejected: ${order.reject_reason}`);
          break;
        case 'cancelled':
          logger.info(`Order ${order.order_id} cancelled`);
          break;
      }
    } catch (error) {
      logger.error('Error handling order update:', error);
    }
  }

  static handleOrderSnapshot(message: WSMessage): void {
    try {
      const payload = message.p;

      logger.info('=== ORDER SNAPSHOT RECEIVED ===');
      logger.info('Orders count:', payload.orders?.length || 0);

      if (!payload.orders || !Array.isArray(payload.orders)) {
        logger.error('Invalid order snapshot format - orders is not an array:', payload);
        return;
      }

      logger.info(`Processing ${payload.orders.length} orders from snapshot`);

      // BEST PRACTICE (TkDodo 2025): WebSocket snapshot → setQueryData (no REST API call)
      // This ensures UI updates INSTANTLY when new orders arrive via WebSocket snapshot
      queryClient.setQueryData(queryKeys.orders.all, payload.orders);
      logger.info('Order cache updated directly from WebSocket snapshot (no REST API call)');

      // Dispatch success event
      window.dispatchEvent(new CustomEvent('orderSnapshotReceived', {
        detail: {
          orders: payload.orders,
          count: payload.orders.length,
          timestamp: new Date().toISOString()
        }
      }));

      logger.info(`Order snapshot processing complete: ${payload.orders.length} orders set`);
    } catch (error) {
      logger.error('Error handling order snapshot:', error);

      window.dispatchEvent(new CustomEvent('orderSnapshotError', {
        detail: {
          error: error instanceof Error ? error.message : String(error),
          timestamp: new Date().toISOString()
        }
      }));
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // System Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleSystemAnnouncement(message: WSMessage): void {
    try {
      const announcement = message.p;

      logger.info('System announcement:', announcement);

      window.dispatchEvent(new CustomEvent('systemAnnouncement', {
        detail: {
          id: announcement.id || crypto.randomUUID(),
          type: announcement.type || 'info',
          title: announcement.title,
          message: announcement.message,
          timestamp: announcement.timestamp || new Date().toISOString(),
          priority: announcement.priority || 'normal',
          dismissible: announcement.dismissible ?? true,
          action: announcement.action,
          expires_at: announcement.expires_at,
        }
      }));

      switch (announcement.type) {
        case 'maintenance':
          logger.warn(`Scheduled maintenance: ${announcement.message}`);
          break;
        case 'error':
          logger.error(`System error announcement: ${announcement.message}`);
          break;
        case 'warning':
          logger.warn(`System warning: ${announcement.message}`);
          break;
      }
    } catch (error) {
      logger.error('Error handling system announcement:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // System Status Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleSystemStatus(message: WSMessage): void {
    try {
      const status = message.p;
      const systemStatusStore = useSystemStatusStore.getState();

      logger.info('System status update received:', status);

      systemStatusStore.setStatus(status);

      window.dispatchEvent(new CustomEvent('systemStatus', {
        detail: status
      }));
    } catch (error) {
      logger.error('Error handling system status:', error);
    }
  }

  static handleSystemHealthUpdate(message: WSMessage): void {
    try {
      const healthData = message.p;
      const systemStatusStore = useSystemStatusStore.getState();

      logger.info('System health update received:', healthData);

      const systemStatus = {
        api: healthData.api_status || healthData.api || 'unknown',
        api_status: healthData.api_status || 'unknown',
        datafeed_status: healthData.datafeed_status || 'unknown',
        redis: healthData.redis_status || healthData.redis || 'unknown',
        event_bus: healthData.event_bus_status || healthData.event_bus || 'unknown',
        cpu_usage: healthData.cpu_usage,
        memory_usage: healthData.memory_usage,
        lastBackup: healthData.last_backup || healthData.lastBackup,
        active_connections: healthData.active_connections,
        event_queue_size: healthData.event_queue_size,
        adapter_statuses: healthData.adapter_statuses,
        module_statuses: healthData.module_statuses,
        circuit_breakers: healthData.circuit_breakers,
        uptime: healthData.uptime,
      };

      systemStatusStore.setStatus(systemStatus);

      window.dispatchEvent(new CustomEvent('systemStatus', {
        detail: systemStatus
      }));
    } catch (error) {
      logger.error('Error handling system health update:', error);
    }
  }

  static handleComponentHealth(message: WSMessage): void {
    try {
      const healthUpdate = message.p;

      logger.info('Component health update received:', healthUpdate);

      if (healthUpdate.component && healthUpdate.status) {
        window.dispatchEvent(new CustomEvent('componentHealth', {
          detail: {
            component: healthUpdate.component,
            status: healthUpdate.status,
            message: healthUpdate.message,
            timestamp: healthUpdate.timestamp || new Date().toISOString(),
          }
        }));
      } else if (healthUpdate.components) {
        Object.entries(healthUpdate.components).forEach(([component, status]) => {
          window.dispatchEvent(new CustomEvent('componentHealth', {
            detail: {
              component,
              status,
              timestamp: healthUpdate.timestamp || new Date().toISOString(),
            }
          }));
        });
      }
    } catch (error) {
      logger.error('Error handling component health:', error);
    }
  }

  static handlePerformanceMetrics(message: WSMessage): void {
    try {
      const metrics = message.p;

      logger.debug('Performance metrics received:', metrics);

      window.dispatchEvent(new CustomEvent('performanceMetrics', {
        detail: {
          cpu_usage: metrics.cpu_usage,
          memory_usage: metrics.memory_usage,
          event_queue_size: metrics.event_queue_size,
          active_connections: metrics.active_connections,
          uptime: metrics.uptime,
          timestamp: metrics.timestamp || new Date().toISOString(),
        }
      }));
    } catch (error) {
      logger.error('Error handling performance metrics:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Market Data Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleMarketDataUpdate(message: WSMessage): void {
    try {
      const marketData = message.p;

      logger.debug('Market data update:', marketData);

      window.dispatchEvent(new CustomEvent('marketDataUpdate', {
        detail: {
          symbol: marketData.symbol,
          price: marketData.price,
          bid: marketData.bid,
          ask: marketData.ask,
          volume: marketData.volume,
          timestamp: marketData.timestamp,
          change: marketData.change,
          change_percent: marketData.change_percent,
          high: marketData.high,
          low: marketData.low,
          open: marketData.open,
          close: marketData.close,
          vwap: marketData.vwap,
          market_state: marketData.market_state,
        }
      }));

      if (marketData.symbol && marketData.price) {
        const accountStore = useBrokerAccountStore.getState();

        accountStore.accounts.forEach(account => {
          if (account.positions) {
            const position = account.positions.find(p => p.symbol === marketData.symbol);
            if (position) {
              const quantity = parseFloat(position.quantity);
              const avgCost = parseFloat(position.avg_cost || '0');
              const newMarketValue = quantity * marketData.price;
              const costBasis = quantity * avgCost;
              const unrealizedPnl = newMarketValue - costBasis;
              const unrealizedPnlPercent = costBasis > 0 ? (unrealizedPnl / costBasis) * 100 : 0;

              const updatedPositions = account.positions.map(p =>
                p.symbol === marketData.symbol
                  ? {
                      ...p,
                      market_value: newMarketValue.toString(),
                      unrealized_pnl: unrealizedPnl.toString(),
                      unrealized_pnl_percent: unrealizedPnlPercent.toString(),
                    }
                  : p
              );

              accountStore.updateAccount({
                ...account,
                positions: updatedPositions,
              });
            }
          }
        });
      }
    } catch (error) {
      logger.error('Error handling market data update:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Streaming Status Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleBrokerStreamingSnapshot(message: WSMessage): void {
    try {
      const payload = message.p;
      const brokerStore = useBrokerConnectionStore.getState();

      console.log('=== BROKER STREAMING SNAPSHOT RECEIVED IN HANDLER ===');
      console.log('Streaming status count:', payload.streaming_status?.length || 0);
      console.log('Full payload:', payload);

      if (!payload.streaming_status || !Array.isArray(payload.streaming_status)) {
        console.error('INVALID broker streaming snapshot format!');
        logger.error('Invalid broker streaming snapshot format');
        return;
      }

      // Log stream types
      const streamTypes = payload.streaming_status.map((s: any) => `${s.broker_id}:${s.stream_type}=${s.status}`);
      console.log('Stream types:', streamTypes);

      // Update broker store with streaming status
      payload.streaming_status.forEach((status: any) => {
        brokerStore.updateStreamingStatus({
          broker_connection_id: status.broker_connection_id,
          broker_id: status.broker_id,
          environment: status.environment,
          stream_type: status.stream_type,
          status: status.status,
        });
      });

      window.dispatchEvent(new CustomEvent('brokerStreamingSnapshotReceived', {
        detail: {
          statuses: payload.streaming_status,
          count: payload.streaming_status.length,
          timestamp: new Date().toISOString()
        }
      }));

      console.log('Broker streaming snapshot processing complete');
    } catch (error) {
      console.error('ERROR handling broker streaming snapshot:', error);
      logger.error('Error handling broker streaming snapshot:', error);
    }
  }

  static handleBrokerStreamingUpdate(message: WSMessage): void {
    try {
      const update = message.p;
      const brokerStore = useBrokerConnectionStore.getState();

      console.log('=== BROKER STREAMING UPDATE (INCREMENTAL) ===');
      console.log('Stream:', `${update.broker_id} ${update.environment} ${update.stream_type} -> ${update.status}`);
      console.log('Incremental update:', update);

      // Update broker store
      brokerStore.updateStreamingStatus({
        broker_connection_id: update.broker_connection_id,
        broker_id: update.broker_id,
        environment: update.environment,
        stream_type: update.stream_type,
        status: update.status,
      });

      window.dispatchEvent(new CustomEvent('brokerStreamingUpdate', {
        detail: update
      }));

      console.log('Broker streaming update processed');
    } catch (error) {
      console.error('ERROR handling broker streaming update:', error);
      logger.error('Error handling broker streaming update:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Register All Handlers
  // ─────────────────────────────────────────────────────────────────────────

  static registerAll(messageProcessor: any): void {
    logger.info('=== REGISTERING ALL EVENT HANDLERS ===');

    try {
      // Broker events
      messageProcessor.registerHandler('broker_connection_update', this.handleBrokerConnectionUpdate);
      messageProcessor.registerHandler('broker_status_update', this.handleBrokerConnectionUpdate);
      messageProcessor.registerHandler('broker_connection_snapshot', this.handleBrokerConnectionSnapshot);
      messageProcessor.registerHandler('broker_status_remove', this.handleBrokerStatusRemove);
      messageProcessor.registerHandler('broker_disconnected', this.handleBrokerDisconnected); // CRITICAL FIX (2025-11-08)
      messageProcessor.registerHandler('broker_connection_established', this.handleBrokerConnectionEstablished); // CRITICAL FIX (2025-11-08)
      messageProcessor.registerHandler('broker_module_health_update', this.handleBrokerModuleHealthUpdate);

      // Health events (NEW - Nov 13, 2025)
      messageProcessor.registerHandler('broker_health_update', this.handleBrokerHealthUpdate);

      // Streaming status events
      messageProcessor.registerHandler('broker_streaming_snapshot', this.handleBrokerStreamingSnapshot);
      messageProcessor.registerHandler('broker_streaming_update', this.handleBrokerStreamingUpdate);

      // Account events
      messageProcessor.registerHandler('broker_account_update', this.handleAccountUpdate);
      messageProcessor.registerHandler('account_update', this.handleAccountUpdate); // Legacy support
      messageProcessor.registerHandler('broker_account_remove', this.handleAccountRemove);
      messageProcessor.registerHandler('account_remove', this.handleAccountRemove); // Legacy support
      messageProcessor.registerHandler('broker_accounts_bulk_remove', this.handleAccountsBulkRemove);
      messageProcessor.registerHandler('accounts_bulk_remove', this.handleAccountsBulkRemove); // Legacy support
      messageProcessor.registerHandler('broker_account_snapshot', this.handleBrokerAccountSnapshot);

      // Automation events
      messageProcessor.registerHandler('automation_update', this.handleAutomationUpdate);
      messageProcessor.registerHandler('automation_snapshot', this.handleAutomationSnapshot);

      // Trading events
      messageProcessor.registerHandler('position_update', this.handlePositionUpdate);
      messageProcessor.registerHandler('order_update', this.handleOrderUpdate);
      messageProcessor.registerHandler('order_snapshot', this.handleOrderSnapshot);

      // System events
      messageProcessor.registerHandler('system_announcement', this.handleSystemAnnouncement);
      messageProcessor.registerHandler('system_status', this.handleSystemStatus);
      messageProcessor.registerHandler('system_health_update', this.handleSystemHealthUpdate);
      messageProcessor.registerHandler('component_health', this.handleComponentHealth);
      messageProcessor.registerHandler('performance_metrics', this.handlePerformanceMetrics);

      // Market data events
      messageProcessor.registerHandler('market_data_update', this.handleMarketDataUpdate);

      logger.info('All event handlers registered successfully');

      // Log the registered handlers for debugging
      const registeredHandlers = messageProcessor.getRegisteredHandlers();
      logger.info('Registered handlers:', registeredHandlers);

    } catch (error) {
      logger.error('Error registering event handlers:', error);
      throw error;
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Broker Module Health Events
  // ─────────────────────────────────────────────────────────────────────────

  static handleBrokerModuleHealthUpdate(message: WSMessage): void {
    try {
      const payload = message.p;
      const brokerStore = useBrokerConnectionStore.getState();

      logger.info('Broker module health update:', payload);

      if (payload.broker_connection_id && payload.module_updates) {
        const connections = brokerStore.getAllConnections();
        const broker = connections.find(
          conn => conn.brokerConnectionId === payload.broker_connection_id
        );

        if (broker) {
          Object.entries(payload.module_updates).forEach(([moduleName, moduleInfo]: [string, any]) => {
            logger.debug(`Module ${moduleName} health:`, moduleInfo);

            window.dispatchEvent(new CustomEvent('brokerModuleHealthUpdate', {
              detail: {
                broker_connection_id: payload.broker_connection_id,
                broker_id: broker.id,
                environment: broker.environment,
                module: moduleName,
                health: moduleInfo
              }
            }));
          });
        }
      }
    } catch (error) {
      logger.error('Error handling broker module health update:', error);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Broker Health Events (NEW - Nov 13, 2025)
  // ─────────────────────────────────────────────────────────────────────────

  static handleBrokerHealthUpdate(message: WSMessage): void {
    try {
      const payload = message.p;
      const brokerStore = useBrokerConnectionStore.getState();

      logger.info('Broker health update:', {
        broker_connection_id: payload.broker_connection_id,
        broker_id: payload.broker_id,
        environment: payload.environment,
        is_healthy: payload.is_healthy,
        health_status: payload.health_status,
        response_time_ms: payload.response_time_ms,
        modules: payload.modules
      });

      // Update broker connection health in store
      if (payload.broker_connection_id) {
        brokerStore.updateHealth(payload.broker_connection_id, {
          is_healthy: payload.is_healthy ?? true,
          health_status: payload.health_status || 'unknown',
          response_time_ms: payload.response_time_ms,
          modules: payload.modules,
          last_checked: payload.last_checked || new Date().toISOString()
        });

        // Dispatch event for UI components
        window.dispatchEvent(new CustomEvent('brokerHealthUpdate', {
          detail: {
            broker_connection_id: payload.broker_connection_id,
            broker_id: payload.broker_id,
            environment: payload.environment,
            is_healthy: payload.is_healthy,
            health_status: payload.health_status,
            response_time_ms: payload.response_time_ms,
            modules: payload.modules,
            message: payload.message,
            last_checked: payload.last_checked
          }
        }));
      }
    } catch (error) {
      logger.error('Error handling broker health update:', error);
    }
  }
}

// Helper functions for status mapping
function mapSnapshotStatus(broker: any): 'connecting' | 'connected' | 'error' {
  const status = broker.status?.toLowerCase() || '';

  if (broker.connected === true ||
      broker.is_healthy === true ||
      status === 'connected' ||
      status === 'healthy' ||
      status === 'active') {
    return 'connected';
  }

  if (status === 'connecting' ||
      status === 'pending' ||
      status === 'initializing' ||
      status === 'authenticating' ||
      status === 'getting_data' ||
      status === 'loading_accounts') {
    return 'connecting';
  }

  return 'error';
}

function formatSnapshotError(broker: any): string | undefined {
  if (broker.connected === true || broker.is_healthy === true) {
    return undefined;
  }

  if (broker.reauth_required) {
    return 'Authentication required.\nPlease reconnect with valid credentials.';
  }

  if (broker.error_message) {
    return broker.error_message;
  }

  if (broker.message) {
    const msg = broker.message.substring(0, 80);
    return msg.length < broker.message.length ? msg + '...' : msg;
  }

  if (broker.status?.toLowerCase() === 'error' ||
      broker.status?.toLowerCase() === 'disconnected' ||
      broker.status?.toLowerCase() === 'failed') {
    return 'Connection failed.\nPlease check your credentials.';
  }

  return undefined;
}