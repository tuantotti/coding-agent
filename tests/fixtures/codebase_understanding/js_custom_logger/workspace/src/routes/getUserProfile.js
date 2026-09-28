const { logger } = require("../lib/logger");
const { AppError } = require("../lib/appError");

function getUserProfile(request) {
  const { userId } = request.params;
  if (!userId) {
    logger.error("getUserProfile called without userId");
    throw new AppError("userId is required", 400);
  }
  logger.info("fetching user profile", { userId });
  return { userId, name: "placeholder" };
}

module.exports = { getUserProfile };
