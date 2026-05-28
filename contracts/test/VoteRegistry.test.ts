import { describe, it } from "node:test";

import { network } from "hardhat";

describe("VoteRegistry", async function () {
  const { viem } = await network.getOrCreate();

  it("publishElection emits ElectionPublished with correct args", async function () {
    const registry = await viem.deployContract("VoteRegistry");

    const electionId = 1n;
    const paramsHash =
      "0x1111111111111111111111111111111111111111111111111111111111111111";

    await viem.assertions.emitWithArgs(
      registry.write.publishElection([electionId, paramsHash]),
      registry,
      "ElectionPublished",
      [electionId, paramsHash],
    );
  });

  it("commitVote emits VoteCommitted with correct args", async function () {
    const registry = await viem.deployContract("VoteRegistry");

    const electionId = 42n;
    const commitment =
      "0x2222222222222222222222222222222222222222222222222222222222222222";

    await viem.assertions.emitWithArgs(
      registry.write.commitVote([electionId, commitment]),
      registry,
      "VoteCommitted",
      [electionId, commitment],
    );
  });

  it("finalizeElection emits ElectionFinalized with correct args", async function () {
    const registry = await viem.deployContract("VoteRegistry");

    const electionId = 7n;
    const merkleRoot =
      "0x3333333333333333333333333333333333333333333333333333333333333333";
    const resultsHash =
      "0x4444444444444444444444444444444444444444444444444444444444444444";

    await viem.assertions.emitWithArgs(
      registry.write.finalizeElection([electionId, merkleRoot, resultsHash]),
      registry,
      "ElectionFinalized",
      [electionId, merkleRoot, resultsHash],
    );
  });
});
