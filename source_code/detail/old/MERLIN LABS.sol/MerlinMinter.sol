// SPDX-License-Identifier: MIT

pragma solidity ^0.6.12;
pragma experimental ABIEncoderV2;

import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@pancakeswap/pancake-swap-lib/contracts/token/BEP20/SafeBEP20.sol";
import "@pancakeswap/pancake-swap-lib/contracts/token/BEP20/BEP20.sol";
import "@pancakeswap/pancake-swap-lib/contracts/token/BEP20/IBEP20.sol";
import "@pancakeswap/pancake-swap-lib/contracts/math/SafeMath.sol";

import "./interface/IPancakePair.sol";
import "./interface/IMerlinMinter.sol";
import "./interface/IStakingRewards.sol";
import "./interface/IZapBSC.sol";
import "./interface/IPancakeRouter02.sol";
import "./interfaces/ILottery.sol";

import "./PriceCalculatorBSC.sol";

contract MerlinMinter is IMerlinMinter, OwnableUpgradeable {
    using SafeMath for uint;
    using SafeBEP20 for IBEP20;

    uint public constant FEE_MAX = 10000;

    /* ========== STATE VARIABLES ========== */

    address public TIMELOCK;
    address public MERLIN;
    address public MERLIN_POOL;
    address public MERLIN_BNB;
    address public DEPLOYER;
    address public WITHDRAWAL_FEE_ACCOUNT;
    IZapBSC public zapBSC;
    IPancakeRouter02 public router;
    PriceCalculatorBSC public priceCalculator;

    mapping(address => bool) private _minters;

    uint public PERFORMANCE_FEE;
    uint public override WITHDRAWAL_FEE_FREE_PERIOD;
    uint public override WITHDRAWAL_FEE;

    uint public override merlinPerProfitBNB;

    address public LOTTERY;

    uint public BURN_CONTRIBUTION;

    uint public LOTTERY_RATIO;
    address public BUYBACKER;

    // merlin chef
    address public merlinChef;

    /* ========== MODIFIERS ========== */

    modifier onlyMinter {
        require(isMinter(msg.sender) == true, "MerlinMiner: caller is not the minter");
        _;
    }

    modifier onlyMerlinChef {
        require(msg.sender == merlinChef, "MerlinMinterV2: caller not the merlin chef");
        _;
    }

    receive() external payable {}

    /* ========== INITIALIZER ========== */
    function initialize(
        address _merlin,
        address _merlinPool,
        address _deployer,
        address _merlinBNB,
        address _zapBSC,
        address _router02,
        address _priceCalculator,
        address _withdrawal_fee_account,
        address _timeLock
    ) external initializer {
        __Ownable_init();

        MERLIN = _merlin;
        MERLIN_POOL = _merlinPool;
        MERLIN_BNB = _merlinBNB;
        DEPLOYER = _deployer;
        WITHDRAWAL_FEE_ACCOUNT = _withdrawal_fee_account;
        TIMELOCK = _timeLock;

        zapBSC = IZapBSC(_zapBSC);
        router = IPancakeRouter02(_router02);
        priceCalculator = PriceCalculatorBSC(_priceCalculator);

        WITHDRAWAL_FEE_FREE_PERIOD = 3 days;
        WITHDRAWAL_FEE = 50;
        PERFORMANCE_FEE = 5000;

        merlinPerProfitBNB = 20e18;

        BURN_CONTRIBUTION = 100;
        LOTTERY_RATIO = 80;

        IBEP20(MERLIN).approve(MERLIN_POOL, uint(-1));
        IBEP20(MERLIN_BNB).approve(MERLIN_POOL, uint(-1));
    }

    /* ========== RESTRICTED FUNCTIONS ========== */

    function transferMerlinOwner(address _owner) external onlyOwner {
        Ownable(MERLIN).transferOwnership(_owner);
    }

    function setWithdrawalFee(uint _fee) external onlyOwner {
        require(_fee < 500, "wrong fee");
        // less 5%
        WITHDRAWAL_FEE = _fee;
    }

    function setPerformanceFee(uint _fee) external onlyOwner {
        require(_fee < 5100, "wrong fee");
        PERFORMANCE_FEE = _fee;
    }

    function setWithdrawalFeeFreePeriod(uint _period) external onlyOwner {
        WITHDRAWAL_FEE_FREE_PERIOD = _period;
    }

    function setMinter(address minter, bool canMint) external override onlyOwner {
        if (canMint) {
            _minters[minter] = canMint;
        } else {
            delete _minters[minter];
        }
    }

    function setMerlinPerProfitBNB(uint _ratio) external onlyOwner {
        merlinPerProfitBNB = _ratio;
    }

    function setMerlinChef(address _merlinChef) external onlyOwner {
        require(merlinChef == address(0), "MerlinMinter: setMerlinChef only once");
        merlinChef = _merlinChef;
    }

    function setTimelock(address _timelock) external onlyOwner {
        require(TIMELOCK == address(0), "MerlinMinter: setTimelock only once");
        TIMELOCK = _timelock;
    }

    function setBurnContribution(uint _burn) external onlyOwner {
        BURN_CONTRIBUTION = _burn;
    }

    function setLottery(address _lottery) external onlyOwner {
        LOTTERY = _lottery;
    }

    function setLotteryRatio(uint _lotteryRatio) external onlyOwner {
        LOTTERY_RATIO = _lotteryRatio;
    }

    function setBuybacker(address _buybacker) external onlyOwner {
        BUYBACKER = _buybacker;
    }

    function setPriceCalculator(address _priceCalculator) external onlyOwner {
        priceCalculator = PriceCalculatorBSC(_priceCalculator);
    }

    /* ========== VIEWS ========== */

    function isMinter(address account) public view override returns (bool) {
        if (IBEP20(MERLIN).getOwner() != address(this)) {
            return false;
        }
        return _minters[account];
    }

    function amountMerlinToMint(uint bnbProfit) public view override returns (uint) {
        return bnbProfit.mul(merlinPerProfitBNB).div(1e18);
    }

    function withdrawalFee(uint amount, uint depositedAt) external view override returns (uint) {
        if (depositedAt.add(WITHDRAWAL_FEE_FREE_PERIOD) > block.timestamp) {
            return amount.mul(WITHDRAWAL_FEE).div(FEE_MAX);
        }
        return 0;
    }

    function performanceFee(uint profit) public view override returns (uint) {
        return profit.mul(PERFORMANCE_FEE).div(FEE_MAX);
    }

    function mintFor(address asset, uint _withdrawalFee, uint _performanceFee, address to, uint) external payable override onlyMinter {
        uint feeSum = _performanceFee.add(_withdrawalFee);
        _transferAsset(asset, feeSum);

        if (asset == MERLIN) {
            IBEP20(MERLIN).safeTransfer(0x000000000000000000000000000000000000dEaD, feeSum);
            return;
        }

        if (_withdrawalFee > 0) {
            IBEP20(asset).approve(address(this), uint(-1));
            IBEP20(asset).safeTransfer(WITHDRAWAL_FEE_ACCOUNT, _withdrawalFee);
        }

        if (_performanceFee == 0) return;

        // Burn performance fee (aka contribution fee)
        uint burnAmount = _performanceFee.mul(BURN_CONTRIBUTION).div(10000);
        _performanceFee = _performanceFee.sub(burnAmount);

        (uint valueInBNB,) = priceCalculator.valueOfAsset(asset, _performanceFee);
        uint contribution = valueInBNB;

        uint amountMerlinBNB = _zapAssetsToMerlinBNB(asset, _performanceFee);
        if (amountMerlinBNB == 0) return;

        IBEP20(MERLIN_BNB).safeTransfer(MERLIN_POOL, amountMerlinBNB);
        IStakingRewards(MERLIN_POOL).notifyRewardAmount(amountMerlinBNB);

        if (burnAmount > 1000) {
            _transferToLotteryAndBuyback(asset, burnAmount);
        }

        uint mintMerlin = amountMerlinToMint(contribution);

        if (mintMerlin == 0) return;
        _mint(mintMerlin, to);
    }

    /* ========== MerlinChef FUNCTIONS ========== */

    function mint(uint amount) external override onlyMerlinChef {
        if (amount == 0) return;
        _mint(amount, address(this));
    }

    function safeMerlinTransfer(address _to, uint _amount) external override onlyMerlinChef {
        if (_amount == 0) return;

        uint bal = IBEP20(MERLIN).balanceOf(address(this));
        if (_amount <= bal) {
            IBEP20(MERLIN).safeTransfer(_to, _amount);
        } else {
            IBEP20(MERLIN).safeTransfer(_to, bal);
        }
    }

    // @dev should be called when determining mint in governance. Merlin is transferred to the timelock contract.
    function mintGov(uint amount) external override onlyOwner {
        if (amount == 0) return;
        _mint(amount, TIMELOCK);
    }

    /* ========== PRIVATE FUNCTIONS ========== */

    function _transferToLotteryAndBuyback(address asset, uint amount) private {
        // uint balanceBefore = IBEP20(MERLIN).balanceOf(address(this));
        IBEP20(asset).approve(address(zapBSC), amount);
        // zapBSC.zapInToken(asset, amount, MERLIN);
        // uint balanceAfter = IBEP20(MERLIN).balanceOf(address(this));
        uint balance = _zapAssetsToMerlin(asset, amount);

        uint lotteryAmount = balance.mul(LOTTERY_RATIO).div(100);
        uint buybackAmount = balance.sub(lotteryAmount);

        // transfer to lottery
        if (LOTTERY != address(0) && lotteryAmount > 1000) {
            IBEP20(MERLIN).approve(LOTTERY, lotteryAmount);
            ILottery(LOTTERY).addMerlinPrize(lotteryAmount);
        }

        // Buy back
        if (buybackAmount > 0) {
            IBEP20(MERLIN).safeTransfer(BUYBACKER, buybackAmount);
        }
    }

    function _transferAsset(address asset, uint amount) private {
        if (asset == address(0)) {
            // case) transferred BNB
            require(msg.value >= amount);
        } else {
            IBEP20(asset).safeTransferFrom(msg.sender, address(this), amount);
        }
    }

    function _zapAssetsToMerlinBNB(address asset, uint amount) private returns (uint merlinBNBAmout) {
        uint _initMerlinBNBAmount = IBEP20(MERLIN_BNB).balanceOf(address(this));

        if (asset == address(0)) {
            zapBSC.zapIn{ value : amount }(MERLIN_BNB);
        }
        else if (keccak256(abi.encodePacked(IPancakePair(asset).symbol())) == keccak256("Cake-LP")) {
            if (IBEP20(asset).allowance(address(this), address(router)) == 0) {
                IBEP20(asset).safeApprove(address(router), uint(- 1));
            }

            IPancakePair pair = IPancakePair(asset);
            address token0 = pair.token0();
            address token1 = pair.token1();

            (uint amountToken0, uint amountToken1) = router.removeLiquidity(token0, token1, amount, 0, 0, address(this), block.timestamp);

            if (IBEP20(token0).allowance(address(this), address(zapBSC)) == 0) {
                IBEP20(token0).safeApprove(address(zapBSC), uint(- 1));
            }
            if (IBEP20(token1).allowance(address(this), address(zapBSC)) == 0) {
                IBEP20(token1).safeApprove(address(zapBSC), uint(- 1));
            }

            zapBSC.zapInToken(token0, amountToken0, MERLIN_BNB);
            zapBSC.zapInToken(token1, amountToken1, MERLIN_BNB);
        }
        else {
            if (IBEP20(asset).allowance(address(this), address(zapBSC)) == 0) {
                IBEP20(asset).safeApprove(address(zapBSC), uint(- 1));
            }

            zapBSC.zapInToken(asset, amount, MERLIN_BNB);
        }

        merlinBNBAmout = IBEP20(MERLIN_BNB).balanceOf(address(this)).sub(_initMerlinBNBAmount);
    }


    function _zapAssetsToMerlin(address asset, uint amount) private returns (uint merlinAmout) {
        uint _initMerlinAmount = IBEP20(MERLIN).balanceOf(address(this));

        if (asset == address(0)) {
            zapBSC.zapIn{ value : amount }(MERLIN);
        }
        else if (keccak256(abi.encodePacked(IPancakePair(asset).symbol())) == keccak256("Cake-LP")) {
            if (IBEP20(asset).allowance(address(this), address(router)) == 0) {
                IBEP20(asset).safeApprove(address(router), uint(- 1));
            }

            IPancakePair pair = IPancakePair(asset);
            address token0 = pair.token0();
            address token1 = pair.token1();

            (uint amountToken0, uint amountToken1) = router.removeLiquidity(token0, token1, amount, 0, 0, address(this), block.timestamp);

            if (IBEP20(token0).allowance(address(this), address(zapBSC)) == 0) {
                IBEP20(token0).safeApprove(address(zapBSC), uint(- 1));
            }
            if (IBEP20(token1).allowance(address(this), address(zapBSC)) == 0) {
                IBEP20(token1).safeApprove(address(zapBSC), uint(- 1));
            }

            zapBSC.zapInToken(token0, amountToken0, MERLIN);
            zapBSC.zapInToken(token1, amountToken1, MERLIN);
        }
        else {
            if (IBEP20(asset).allowance(address(this), address(zapBSC)) == 0) {
                IBEP20(asset).safeApprove(address(zapBSC), uint(- 1));
            }

            zapBSC.zapInToken(asset, amount, MERLIN);
        }

        merlinAmout = IBEP20(MERLIN).balanceOf(address(this)).sub(_initMerlinAmount);
    }

    function _mint(uint amount, address to) private {
        BEP20 tokenMERLIN = BEP20(MERLIN);

        tokenMERLIN.mint(amount);
        if (to != address(this)) {
            tokenMERLIN.transfer(to, amount);
        }

        uint merlinForDev = amount.mul(13).div(100);
        tokenMERLIN.mint(merlinForDev);
        IStakingRewards(MERLIN_POOL).stakeTo(merlinForDev, DEPLOYER);
    }
}
