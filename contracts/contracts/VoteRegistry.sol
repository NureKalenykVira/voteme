// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract VoteRegistry {
    event ElectionPublished(uint256 indexed electionId, bytes32 paramsHash);
    event VoteCommitted(uint256 indexed electionId, bytes32 commitment);
    event ElectionFinalized(uint256 indexed electionId, bytes32 merkleRoot, bytes32 resultsHash);

    function publishElection(uint256 electionId, bytes32 paramsHash) external {
        emit ElectionPublished(electionId, paramsHash);
    }

    function commitVote(uint256 electionId, bytes32 commitment) external {
        emit VoteCommitted(electionId, commitment);
    }

    function finalizeElection(uint256 electionId, bytes32 merkleRoot, bytes32 resultsHash) external {
        emit ElectionFinalized(electionId, merkleRoot, resultsHash);
    }
}
