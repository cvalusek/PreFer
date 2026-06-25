import type { AuthenticatedUser } from "../domain/types.js";

declare module "fastify" {
  interface FastifyRequest {
    user?: AuthenticatedUser;
  }
}
