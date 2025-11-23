import React, { useState, useEffect } from 'react';

/**
 * SessionIndicator Component
 *
 * Visual indicator showing:
 * - Session active/inactive status
 * - Time remaining until auto-flush
 * - Manual "Save Now" button
 *
 * Design decisions:
 * - Green dot = active session
 * - Timer counts down from 5:00 to 0:00
 * - Shows warning when <1 minute remaining
 * - Manual flush button for user control
 */
const SessionIndicator = ({ isActive, getTimeRemaining, onFlush }) => {
  const [timeRemaining, setTimeRemaining] = useState(0);

  // Update time remaining every second
  useEffect(() => {
    if (!isActive) {
      setTimeRemaining(0);
      return;
    }

    // Update immediately
    setTimeRemaining(getTimeRemaining());

    // Then update every second
    const interval = setInterval(() => {
      const remaining = getTimeRemaining();
      setTimeRemaining(remaining);

      // If time expired, clear interval
      if (remaining <= 0) {
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isActive, getTimeRemaining]);

  if (!isActive) return null;

  // Convert ms to mm:ss
  const minutes = Math.floor(timeRemaining / 60000);
  const seconds = Math.floor((timeRemaining % 60000) / 1000);
  const timeString = `${minutes}:${seconds.toString().padStart(2, '0')}`;

  // Warning state if <1 minute remaining
  const isWarning = minutes < 1;

  return (
    <div
      className="alert d-flex align-items-center justify-content-between"
      style={{
        backgroundColor: isWarning ? '#fff3cd' : '#d1ecf1',
        borderColor: isWarning ? '#ffc107' : '#17a2b8',
        padding: '8px 16px',
        marginBottom: '16px',
        borderRadius: '4px',
      }}
    >
      <div className="d-flex align-items-center">
        {/* Status dot */}
        <span
          className="status-dot"
          style={{
            display: 'inline-block',
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            backgroundColor: isWarning ? '#ffc107' : '#28a745',
            marginRight: '12px',
            animation: 'pulse 2s infinite',
          }}
        />

        {/* Status text */}
        <span style={{ fontSize: '14px' }}>
          <strong>Session active</strong> — Changes will be saved when session ends
          {timeRemaining > 0 && (
            <span
              style={{
                marginLeft: '8px',
                color: isWarning ? '#856404' : '#0c5460',
              }}
            >
              ({timeString} remaining)
            </span>
          )}
        </span>
      </div>

      {/* Manual flush button */}
      {onFlush && (
        <button
          className="btn btn-sm btn-outline-primary"
          onClick={onFlush}
          style={{ padding: '4px 12px', fontSize: '13px' }}
        >
          Save Now
        </button>
      )}

      {/* CSS animation for pulsing dot */}
      <style>
        {`
          @keyframes pulse {
            0%, 100% {
              opacity: 1;
            }
            50% {
              opacity: 0.5;
            }
          }
        `}
      </style>
    </div>
  );
};

export default SessionIndicator;
