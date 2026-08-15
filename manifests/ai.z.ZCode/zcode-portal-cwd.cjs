'use strict';

const fs = require('node:fs');

const originalCwd = process.cwd.bind(process);
const deletedSuffix = ' (deleted)';

process.cwd = function portalAwareCwd() {
  try {
    return originalCwd();
  } catch (error) {
    if (error?.code !== 'ENOENT')
      throw error;

    try {
      const procCwd = fs.readlinkSync('/proc/self/cwd');
      if (!procCwd.endsWith(deletedSuffix))
        throw error;

      const fallbackCwd = procCwd.slice(0, -deletedSuffix.length);
      if (!fallbackCwd.startsWith('/run/flatpak/doc/'))
        throw error;

      const current = fs.statSync('.', { bigint: true });
      const fallback = fs.statSync(fallbackCwd, { bigint: true });

      if (current.dev !== fallback.dev || current.ino !== fallback.ino)
        throw error;

      return fallbackCwd;
    } catch {
      throw error;
    }
  }
};
