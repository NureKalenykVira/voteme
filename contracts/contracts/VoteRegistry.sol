// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract VoteRegistry {
    event ElectionPublished(uint256 indexed electionId, bytes32 paramsHash);
    event VoteCommitted(uint256 indexed electionId, bytes32 commitment);
    event ElectionFinalized(uint256 indexed electionId, bytes32 merkleRoot, bytes32 resultsHash);
}
