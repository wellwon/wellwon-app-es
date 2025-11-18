// =============================================================================
// File: src/hooks/useOauth.ts — TradeCore v0.3 (Synapse)
// =============================================================================
// • Handles token lifecycle: status, refresh, revoke
// • For use across BrokerCard, BrokerForm, and reconnect flows
// • Fully separated from broker connection logic (SRP)
// =============================================================================

import { useCallback } from "react";
import {
  getAccessTokenStatus,
  refreshAccessToken,
  revokeRefreshToken,
} from "@/api/oauth";

import { BrokerEnvironment } from "@/types/broker.types";

export function useOauth() {
  const checkAccessToken = useCallback(
    async (broker_id: string, environment: BrokerEnvironment) => {
      try {
        const { valid, reason } = await getAccessTokenStatus(broker_id, environment);
        return { valid, reason };
      } catch (err) {
        return { valid: false, reason: "Request failed" };
      }
    },
    []
  );

  const refreshAccessTokenNow = useCallback(
    async (broker_id: string, environment: BrokerEnvironment) => {
      try {
        const { access_token, expires_in } = await refreshAccessToken(broker_id, environment);
        return { access_token, expires_in };
      } catch (err) {
        return null;
      }
    },
    []
  );

  const revokeRefreshTokenNow = useCallback(
    async (broker_id: string, environment: BrokerEnvironment) => {
      try {
        const res = await revokeRefreshToken(broker_id, environment);
        return res.status === "success";
      } catch (err) {
        return false;
      }
    },
    []
  );

  return {
    checkAccessToken,
    refreshAccessTokenNow,
    revokeRefreshTokenNow,
  };
}