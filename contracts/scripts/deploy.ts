import { network } from "hardhat";

async function main() {
  const connection = await network.create("sepolia");
  const { viem } = connection;

  console.log("Deploying VoteRegistry to Sepolia...");

  const registry = await viem.deployContract("VoteRegistry");

  console.log(`VoteRegistry deployed at: ${registry.address}`);

  await connection.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});