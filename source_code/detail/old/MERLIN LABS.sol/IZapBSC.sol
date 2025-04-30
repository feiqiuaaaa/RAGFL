// SPDX-License-Identifier: MIT
pragma solidity ^0.6.12;
// pragma experimental ABIEncoderV2;

interface IZapBSC {
    function zapIn(address _to) external payable;
    function zapOut(address _from, uint amount) external;
    function zapInToken(address _from, uint amount, address _to) external;
}